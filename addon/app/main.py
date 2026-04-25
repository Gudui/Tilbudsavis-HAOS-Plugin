from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from app.config import Settings, get_settings
from app.db import Database
from app.models import WatchedProduct
from app.providers.registry import build_enabled_providers
from app.services.queries import build_dashboard, filter_matches, group_matches, sort_matches
from app.services.sync import list_provider_health, run_sync


class WatchedProductPayload(BaseModel):
    name: str = Field(min_length=1)
    keywords: list[str] = Field(default_factory=list)
    exclude_keywords: list[str] = Field(default_factory=list)
    max_price: float | None = None
    store_filters: list[str] = Field(default_factory=list)
    enabled: bool = True


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or get_settings()
    base_dir = Path(__file__).resolve().parent
    templates = Jinja2Templates(directory=str(base_dir / "templates"))

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        database: Database = app.state.db
        database.initialize()
        if app.state.settings.clear_seed_data:
            database.clear_seeded_state()
        if "mock" in app.state.settings.providers:
            database.maybe_seed_watched_products()
        yield

    app = FastAPI(title="Offer Radar", version="0.2.0", lifespan=lifespan)
    app.state.settings = app_settings
    app.state.db = Database(app_settings.database_path)
    app.mount("/static", StaticFiles(directory=str(base_dir / "static")), name="static")

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={"request": request, "settings": app.state.settings},
        )

    @app.get("/sw.js")
    def service_worker() -> FileResponse:
        return FileResponse(base_dir / "static" / "sw.js", media_type="application/javascript")

    @app.get("/health")
    def health() -> dict:
        database: Database = app.state.db
        database.initialize()
        return {
            "status": "ok",
            "providers": app.state.settings.providers,
            "database_path": str(app.state.settings.database_path),
            "last_sync": database.get_last_sync_run(),
        }

    @app.get("/api/providers")
    def providers() -> dict:
        return {"providers": list_provider_health(app.state.db, app.state.settings)}

    @app.get("/api/providers/{provider}/health")
    def provider_health(provider: str) -> dict:
        snapshot = next(
            (item for item in list_provider_health(app.state.db, app.state.settings) if item["provider"] == provider),
            None,
        )
        if not snapshot:
            raise HTTPException(status_code=404, detail="Unknown provider")
        return snapshot

    @app.get("/api/sync-runs")
    def sync_runs(provider: str | None = None, limit: int = 50) -> dict:
        return {"sync_runs": app.state.db.list_sync_runs(limit=limit, provider=provider)}

    @app.get("/api/dashboard")
    def dashboard() -> dict:
        database: Database = app.state.db
        dashboard_payload = build_dashboard(database.list_match_rows())
        dashboard_payload["providers"] = list_provider_health(database, app.state.settings)
        return dashboard_payload

    @app.get("/api/watched-products")
    def list_watched_products() -> list[dict]:
        return [asdict(watch) for watch in app.state.db.list_watched_products()]

    @app.post("/api/watched-products")
    def create_watched_product(payload: WatchedProductPayload) -> dict:
        watch = WatchedProduct(
            id=str(uuid.uuid4()),
            name=payload.name.strip(),
            keywords=payload.keywords,
            exclude_keywords=payload.exclude_keywords,
            max_price=payload.max_price,
            store_filters=payload.store_filters,
            enabled=payload.enabled,
        )
        app.state.db.upsert_watched_product(watch)
        return asdict(watch)

    @app.put("/api/watched-products/{product_id}")
    def update_watched_product(product_id: str, payload: WatchedProductPayload) -> dict:
        existing = app.state.db.get_watched_product(product_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Watched product not found")
        watch = WatchedProduct(
            id=product_id,
            name=payload.name.strip(),
            keywords=payload.keywords,
            exclude_keywords=payload.exclude_keywords,
            max_price=payload.max_price,
            store_filters=payload.store_filters,
            enabled=payload.enabled,
        )
        app.state.db.upsert_watched_product(watch)
        return asdict(watch)

    @app.delete("/api/watched-products/{product_id}")
    def delete_watched_product(product_id: str) -> dict:
        deleted = app.state.db.delete_watched_product(product_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Watched product not found")
        return {"deleted": True}

    @app.get("/api/matches")
    def list_matches(
        status: str = "all",
        store: str | None = None,
        watched_product_id: str | None = None,
        query: str | None = None,
        max_price: float | None = None,
        provider: str | None = None,
    ) -> dict:
        matches = filter_matches(
            app.state.db.list_match_rows(),
            status=status,
            store_slug=store,
            watched_product_id=watched_product_id,
            query=query,
            max_price=max_price,
            provider=provider,
        )
        return {"matches": sort_matches(matches, by="score")}

    @app.get("/api/matches/grouped")
    def grouped_matches(
        by: str = Query(pattern="^(store|product)$"),
        status: str = "active",
        provider: str | None = None,
    ) -> dict:
        matches = filter_matches(app.state.db.list_match_rows(), status=status, provider=provider)
        return {"groups": group_matches(matches, by=by)}

    @app.get("/api/matches/sorted")
    def sorted_matches(
        by: str = Query(pattern="^(price|expires|score)$"),
        status: str = "active",
        provider: str | None = None,
    ) -> dict:
        matches = filter_matches(app.state.db.list_match_rows(), status=status, provider=provider)
        return {"matches": sort_matches(matches, by=by)}

    @app.get("/api/stores")
    def stores(provider: str | None = None) -> dict:
        active_matches = filter_matches(app.state.db.list_match_rows(), status="active", provider=provider)
        groups = group_matches(active_matches, by="store")
        return {
            "stores": [
                {
                    "slug": group["key"],
                    "name": group["subtitle"],
                    "chain": group["title"],
                    "match_count": group["match_count"],
                }
                for group in groups
            ]
        }

    @app.get("/api/stores/{store_slug}/matches")
    def store_matches(store_slug: str, status: str = "active", provider: str | None = None) -> dict:
        matches = filter_matches(
            app.state.db.list_match_rows(),
            status=status,
            store_slug=store_slug,
            provider=provider,
        )
        return {"store": store_slug, "matches": sort_matches(matches, by="score")}

    @app.get("/api/watched-products/{product_id}/matches")
    def watched_product_matches(product_id: str, status: str = "all", provider: str | None = None) -> dict:
        matches = filter_matches(
            app.state.db.list_match_rows(),
            status=status,
            watched_product_id=product_id,
            provider=provider,
        )
        return {"watched_product_id": product_id, "matches": sort_matches(matches, by="price")}

    @app.post("/api/sync")
    def sync(provider: str | None = None) -> dict:
        if provider:
            try:
                build_enabled_providers(app.state.settings, provider)
            except KeyError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
        return run_sync(app.state.db, app.state.settings, selected_provider=provider)

    return app


app = create_app()
