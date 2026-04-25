from __future__ import annotations

import uuid
from dataclasses import asdict
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from app.config import Settings, get_settings
from app.db import Database
from app.models import WatchedProduct
from app.providers.base import ProviderError
from app.providers.etilbudsavis import EtilbudsavisProvider
from app.providers.fixtures import MockFixtureProvider
from app.services.matching import build_matches
from app.services.queries import build_dashboard, filter_matches, group_matches, sort_matches


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
        if app.state.settings.provider == "mock":
            database.maybe_seed_watched_products()
        yield

    app = FastAPI(title="Offer Radar", version="0.1.0", lifespan=lifespan)
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
            "provider": app.state.settings.provider,
            "database_path": str(app.state.settings.database_path),
            "last_sync": database.get_last_sync_run(),
        }

    @app.get("/api/dashboard")
    def dashboard() -> dict:
        database: Database = app.state.db
        return build_dashboard(database.list_match_rows())

    @app.get("/api/watched-products")
    def list_watched_products() -> list[dict]:
        database: Database = app.state.db
        return [asdict(watch) for watch in database.list_watched_products()]

    @app.post("/api/watched-products")
    def create_watched_product(payload: WatchedProductPayload) -> dict:
        database: Database = app.state.db
        watch = WatchedProduct(
            id=str(uuid.uuid4()),
            name=payload.name.strip(),
            keywords=payload.keywords,
            exclude_keywords=payload.exclude_keywords,
            max_price=payload.max_price,
            store_filters=payload.store_filters,
            enabled=payload.enabled,
        )
        database.upsert_watched_product(watch)
        return asdict(watch)

    @app.put("/api/watched-products/{product_id}")
    def update_watched_product(product_id: str, payload: WatchedProductPayload) -> dict:
        database: Database = app.state.db
        existing = database.get_watched_product(product_id)
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
        database.upsert_watched_product(watch)
        return asdict(watch)

    @app.delete("/api/watched-products/{product_id}")
    def delete_watched_product(product_id: str) -> dict:
        database: Database = app.state.db
        deleted = database.delete_watched_product(product_id)
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
    ) -> dict:
        database: Database = app.state.db
        matches = filter_matches(
            database.list_match_rows(),
            status=status,
            store_slug=store,
            watched_product_id=watched_product_id,
            query=query,
            max_price=max_price,
        )
        return {"matches": sort_matches(matches, by="score")}

    @app.get("/api/matches/grouped")
    def grouped_matches(by: str = Query(pattern="^(store|product)$"), status: str = "active") -> dict:
        database: Database = app.state.db
        matches = filter_matches(database.list_match_rows(), status=status)
        return {"groups": group_matches(matches, by=by)}

    @app.get("/api/matches/sorted")
    def sorted_matches(by: str = Query(pattern="^(price|expires|score)$"), status: str = "active") -> dict:
        database: Database = app.state.db
        matches = filter_matches(database.list_match_rows(), status=status)
        return {"matches": sort_matches(matches, by=by)}

    @app.get("/api/stores")
    def stores() -> dict:
        database: Database = app.state.db
        active_matches = filter_matches(database.list_match_rows(), status="active")
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
    def store_matches(store_slug: str, status: str = "active") -> dict:
        database: Database = app.state.db
        matches = filter_matches(database.list_match_rows(), status=status, store_slug=store_slug)
        return {"store": store_slug, "matches": sort_matches(matches, by="score")}

    @app.get("/api/watched-products/{product_id}/matches")
    def watched_product_matches(product_id: str, status: str = "all") -> dict:
        database: Database = app.state.db
        matches = filter_matches(database.list_match_rows(), status=status, watched_product_id=product_id)
        return {"watched_product_id": product_id, "matches": sort_matches(matches, by="price")}

    @app.post("/api/sync")
    def sync() -> dict:
        database: Database = app.state.db
        watched_products = database.list_watched_products()
        if not watched_products:
            database.record_sync_run(
                provider=app.state.settings.provider,
                status="skipped",
                offers_fetched=0,
                matches_created=0,
                error="No watched products configured.",
            )
            return {"status": "skipped", "offers_fetched": 0, "matches_created": 0, "error": "No watched products configured."}

        provider = get_provider(app.state.settings)
        try:
            offers = provider.fetch_offers(watched_products)
            database.upsert_offers(offers)
            matches = build_matches(watched_products, database.list_offers())
            database.replace_matches(matches)
            summary = database.record_sync_run(
                provider=provider.provider_name,
                status="ok",
                offers_fetched=len(offers),
                matches_created=len(matches),
            )
            return summary
        except ProviderError as exc:
            summary = database.record_sync_run(
                provider=provider.provider_name,
                status="error",
                offers_fetched=0,
                matches_created=0,
                error=str(exc),
            )
            return summary

    return app


def get_provider(settings: Settings):
    if settings.provider == "etilbudsavis":
        return EtilbudsavisProvider(settings)
    return MockFixtureProvider(settings.fixture_dir)


app = create_app()
