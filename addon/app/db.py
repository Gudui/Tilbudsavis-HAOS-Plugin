from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from .models import MatchRecord, NormalizedOffer, WatchedProduct


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _from_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


class Database:
    def __init__(self, db_path: Path):
        self.db_path = db_path

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                PRAGMA journal_mode = WAL;

                CREATE TABLE IF NOT EXISTS watched_products (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    keywords_json TEXT NOT NULL,
                    exclude_keywords_json TEXT NOT NULL,
                    max_price REAL,
                    store_filters_json TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS offers (
                    id TEXT PRIMARY KEY,
                    provider TEXT NOT NULL,
                    provider_offer_id TEXT,
                    title TEXT NOT NULL,
                    description TEXT,
                    price REAL,
                    currency TEXT,
                    unit_text TEXT,
                    store_name TEXT NOT NULL,
                    store_chain TEXT,
                    store_slug TEXT NOT NULL,
                    store_id TEXT,
                    image_url TEXT,
                    valid_from TEXT,
                    valid_until TEXT,
                    source_url TEXT,
                    catalog_url TEXT,
                    page_number INTEGER,
                    raw_json TEXT NOT NULL,
                    normalized_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS matches (
                    id TEXT PRIMARY KEY,
                    watched_product_id TEXT NOT NULL REFERENCES watched_products(id) ON DELETE CASCADE,
                    offer_id TEXT NOT NULL REFERENCES offers(id) ON DELETE CASCADE,
                    status TEXT NOT NULL,
                    score REAL NOT NULL,
                    reasons_json TEXT NOT NULL,
                    matched_keywords_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS sync_runs (
                    id TEXT PRIMARY KEY,
                    provider TEXT NOT NULL,
                    status TEXT NOT NULL,
                    catalogs_discovered INTEGER NOT NULL DEFAULT 0,
                    offers_fetched INTEGER NOT NULL DEFAULT 0,
                    normalized_offers_saved INTEGER NOT NULL DEFAULT 0,
                    raw_payloads_persisted INTEGER NOT NULL DEFAULT 0,
                    matches_created INTEGER NOT NULL DEFAULT 0,
                    error_count INTEGER NOT NULL DEFAULT 0,
                    warnings_json TEXT NOT NULL DEFAULT '[]',
                    errors_json TEXT NOT NULL DEFAULT '[]',
                    error TEXT,
                    schema_drift_warning TEXT,
                    duration_ms INTEGER NOT NULL DEFAULT 0,
                    started_at TEXT NOT NULL,
                    completed_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_matches_status ON matches(status);
                CREATE INDEX IF NOT EXISTS idx_matches_watch ON matches(watched_product_id);
                CREATE INDEX IF NOT EXISTS idx_offers_store_slug ON offers(store_slug);
                CREATE INDEX IF NOT EXISTS idx_offers_provider ON offers(provider);
                CREATE INDEX IF NOT EXISTS idx_sync_runs_provider ON sync_runs(provider);
                """
            )
            self._ensure_column(conn, "offers", "provider_offer_id", "TEXT")
            self._ensure_column(conn, "offers", "unit_text", "TEXT")
            self._ensure_column(conn, "offers", "store_id", "TEXT")
            self._ensure_column(conn, "offers", "catalog_url", "TEXT")
            self._ensure_column(conn, "offers", "page_number", "INTEGER")
            self._ensure_column(conn, "sync_runs", "catalogs_discovered", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column(conn, "sync_runs", "normalized_offers_saved", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column(conn, "sync_runs", "raw_payloads_persisted", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column(conn, "sync_runs", "error_count", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column(conn, "sync_runs", "warnings_json", "TEXT NOT NULL DEFAULT '[]'")
            self._ensure_column(conn, "sync_runs", "errors_json", "TEXT NOT NULL DEFAULT '[]'")
            self._ensure_column(conn, "sync_runs", "schema_drift_warning", "TEXT")
            self._ensure_column(conn, "sync_runs", "duration_ms", "INTEGER NOT NULL DEFAULT 0")

    def list_watched_products(self) -> list[WatchedProduct]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, name, keywords_json, exclude_keywords_json, max_price, store_filters_json, enabled
                FROM watched_products
                ORDER BY name COLLATE NOCASE
                """
            ).fetchall()
        return [self._row_to_watch(row) for row in rows]

    def get_watched_product(self, product_id: str) -> WatchedProduct | None:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT id, name, keywords_json, exclude_keywords_json, max_price, store_filters_json, enabled
                FROM watched_products
                WHERE id = ?
                """,
                (product_id,),
            ).fetchone()
        return self._row_to_watch(row) if row else None

    def upsert_watched_product(self, watch: WatchedProduct) -> WatchedProduct:
        timestamp = _utc_now()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO watched_products (
                    id, name, keywords_json, exclude_keywords_json, max_price, store_filters_json, enabled, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    keywords_json = excluded.keywords_json,
                    exclude_keywords_json = excluded.exclude_keywords_json,
                    max_price = excluded.max_price,
                    store_filters_json = excluded.store_filters_json,
                    enabled = excluded.enabled,
                    updated_at = excluded.updated_at
                """,
                (
                    watch.id,
                    watch.name,
                    json.dumps(watch.keywords),
                    json.dumps(watch.exclude_keywords),
                    watch.max_price,
                    json.dumps(watch.store_filters),
                    1 if watch.enabled else 0,
                    timestamp,
                    timestamp,
                ),
            )
        return watch

    def delete_watched_product(self, product_id: str) -> bool:
        with self.connect() as conn:
            result = conn.execute("DELETE FROM watched_products WHERE id = ?", (product_id,))
        return result.rowcount > 0

    def maybe_seed_watched_products(self) -> list[WatchedProduct]:
        watches = self.list_watched_products()
        if watches:
            return watches

        starter = [
            WatchedProduct(
                id=str(uuid.uuid4()),
                name="Pepsi Max",
                keywords=["pepsi max", "1,5 l"],
                max_price=15.0,
            ),
            WatchedProduct(
                id=str(uuid.uuid4()),
                name="Kaffe",
                keywords=["kaffe", "formalede"],
                exclude_keywords=["instant"],
                max_price=55.0,
            ),
            WatchedProduct(
                id=str(uuid.uuid4()),
                name="Bleer",
                keywords=["bleer", "str. 4", "pampers"],
                max_price=99.0,
            ),
        ]
        for watch in starter:
            self.upsert_watched_product(watch)
        return starter

    def clear_seeded_state(self) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM matches")
            conn.execute("DELETE FROM offers")
            conn.execute("DELETE FROM sync_runs")
            conn.execute("DELETE FROM watched_products")

    def upsert_offers(self, offers: list[NormalizedOffer]) -> None:
        if not offers:
            return
        payload = [
            (
                offer.id,
                offer.provider,
                offer.provider_offer_id,
                offer.title,
                offer.description,
                offer.price,
                offer.currency,
                offer.unit_text,
                offer.store_name,
                offer.store_chain,
                offer.store_slug,
                offer.store_id,
                offer.image_url,
                _to_iso(offer.valid_from),
                _to_iso(offer.valid_until),
                offer.source_url,
                offer.catalog_url,
                offer.page_number,
                json.dumps(offer.raw),
                _utc_now(),
            )
            for offer in offers
        ]
        with self.connect() as conn:
            conn.executemany(
                """
                INSERT INTO offers (
                    id, provider, provider_offer_id, title, description, price, currency, unit_text, store_name, store_chain,
                    store_slug, store_id, image_url, valid_from, valid_until, source_url, catalog_url, page_number, raw_json, normalized_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    provider = excluded.provider,
                    provider_offer_id = excluded.provider_offer_id,
                    title = excluded.title,
                    description = excluded.description,
                    price = excluded.price,
                    currency = excluded.currency,
                    unit_text = excluded.unit_text,
                    store_name = excluded.store_name,
                    store_chain = excluded.store_chain,
                    store_slug = excluded.store_slug,
                    store_id = excluded.store_id,
                    image_url = excluded.image_url,
                    valid_from = excluded.valid_from,
                    valid_until = excluded.valid_until,
                    source_url = excluded.source_url,
                    catalog_url = excluded.catalog_url,
                    page_number = excluded.page_number,
                    raw_json = excluded.raw_json,
                    normalized_at = excluded.normalized_at
                """,
                payload,
            )

    def list_offers(self) -> list[NormalizedOffer]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, provider, provider_offer_id, title, description, price, currency, unit_text, store_name, store_chain,
                       store_slug, store_id, image_url, valid_from, valid_until, source_url, catalog_url, page_number, raw_json
                FROM offers
                ORDER BY title COLLATE NOCASE
                """
            ).fetchall()
        return [self._row_to_offer(row) for row in rows]

    def replace_matches(self, matches: list[MatchRecord]) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM matches")
            conn.executemany(
                """
                INSERT INTO matches (
                    id, watched_product_id, offer_id, status, score, reasons_json, matched_keywords_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        match.id,
                        match.watched_product_id,
                        match.offer_id,
                        match.status,
                        match.score,
                        json.dumps(match.reasons),
                        json.dumps(match.matched_keywords),
                        _utc_now(),
                    )
                    for match in matches
                ],
            )

    def record_sync_run(
        self,
        *,
        provider: str,
        status: str,
        catalogs_discovered: int = 0,
        provider_offers_fetched: int = 0,
        normalized_offers_saved: int = 0,
        raw_payloads_persisted: int = 0,
        matches_created: int = 0,
        error_count: int = 0,
        warnings: list[str] | None = None,
        errors: list[str] | None = None,
        error: str | None = None,
        schema_drift_warning: str | None = None,
        duration_ms: int = 0,
    ) -> dict[str, str | int | None | list[str]]:
        sync_id = str(uuid.uuid4())
        started_at = _utc_now()
        completed_at = _utc_now()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO sync_runs (
                    id, provider, status, catalogs_discovered, offers_fetched, normalized_offers_saved,
                    raw_payloads_persisted, matches_created, error_count, warnings_json, errors_json, error,
                    schema_drift_warning, duration_ms, started_at, completed_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sync_id,
                    provider,
                    status,
                    catalogs_discovered,
                    provider_offers_fetched,
                    normalized_offers_saved,
                    raw_payloads_persisted,
                    matches_created,
                    error_count,
                    json.dumps(warnings or []),
                    json.dumps(errors or []),
                    error,
                    schema_drift_warning,
                    duration_ms,
                    started_at,
                    completed_at,
                ),
            )
        return {
            "id": sync_id,
            "provider": provider,
            "status": status,
            "catalogs_discovered": catalogs_discovered,
            "offers_fetched": provider_offers_fetched,
            "normalized_offers_saved": normalized_offers_saved,
            "raw_payloads_persisted": raw_payloads_persisted,
            "matches_created": matches_created,
            "error_count": error_count,
            "warnings": warnings or [],
            "errors": errors or [],
            "error": error,
            "schema_drift_warning": schema_drift_warning,
            "duration_ms": duration_ms,
            "started_at": started_at,
            "completed_at": completed_at,
        }

    def list_sync_runs(self, limit: int = 50, provider: str | None = None) -> list[dict]:
        with self.connect() as conn:
            if provider:
                rows = conn.execute(
                    """
                    SELECT *
                    FROM sync_runs
                    WHERE provider = ?
                    ORDER BY completed_at DESC
                    LIMIT ?
                    """,
                    (provider, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT *
                    FROM sync_runs
                    ORDER BY completed_at DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
        return [self._row_to_sync_run(row) for row in rows]

    def get_last_sync_run(self, provider: str | None = None) -> dict | None:
        runs = self.list_sync_runs(limit=1, provider=provider)
        return runs[0] if runs else None

    def list_provider_snapshots(self, enabled_providers: list[str], known_providers: list[str]) -> list[dict]:
        with self.connect() as conn:
            raw_rows = conn.execute("SELECT * FROM sync_runs ORDER BY completed_at DESC").fetchall()
            offer_counts = {
                row["provider"]: row["count"]
                for row in conn.execute(
                    "SELECT provider, COUNT(*) AS count FROM offers GROUP BY provider"
                ).fetchall()
            }

        latest_by_provider: dict[str, dict] = {}
        last_success_by_provider: dict[str, dict] = {}
        for row in raw_rows:
            converted = self._row_to_sync_run(row)
            latest_by_provider.setdefault(converted["provider"], converted)
            if converted["status"] in {"ok", "degraded"}:
                last_success_by_provider.setdefault(converted["provider"], converted)

        snapshots: list[dict] = []
        for provider in known_providers:
            enabled = provider in enabled_providers
            latest = latest_by_provider.get(provider)
            last_success = last_success_by_provider.get(provider)
            if not enabled:
                status = "disabled"
            elif latest is None:
                status = "degraded"
            else:
                status = latest["status"]
            snapshots.append(
                {
                    "provider": provider,
                    "enabled": enabled,
                    "status": status,
                    "last_sync": latest,
                    "last_successful_sync_at": last_success["completed_at"] if last_success else None,
                    "last_error": latest["error"] if latest else None,
                    "last_schema_drift_warning": latest["schema_drift_warning"] if latest else None,
                    "raw_payload_count": offer_counts.get(provider, 0),
                }
            )
        return snapshots

    def list_match_rows(self) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    m.id,
                    m.status,
                    m.score,
                    m.reasons_json,
                    m.matched_keywords_json,
                    w.id AS watched_product_id,
                    w.name AS watched_product_name,
                    w.max_price AS watched_product_max_price,
                    o.id AS offer_id,
                    o.provider,
                    o.provider_offer_id,
                    o.title,
                    o.description,
                    o.price,
                    o.currency,
                    o.unit_text,
                    o.store_name,
                    o.store_chain,
                    o.store_slug,
                    o.store_id,
                    o.image_url,
                    o.valid_from,
                    o.valid_until,
                    o.source_url,
                    o.catalog_url,
                    o.page_number,
                    o.raw_json
                FROM matches m
                JOIN watched_products w ON w.id = m.watched_product_id
                JOIN offers o ON o.id = m.offer_id
                ORDER BY m.score DESC, o.title COLLATE NOCASE
                """
            ).fetchall()
        return [self._row_to_match_payload(row) for row in rows]

    @staticmethod
    def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
        columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        if column not in columns:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    @staticmethod
    def _row_to_watch(row: sqlite3.Row) -> WatchedProduct:
        return WatchedProduct(
            id=row["id"],
            name=row["name"],
            keywords=json.loads(row["keywords_json"]),
            exclude_keywords=json.loads(row["exclude_keywords_json"]),
            max_price=row["max_price"],
            store_filters=json.loads(row["store_filters_json"]),
            enabled=bool(row["enabled"]),
        )

    @staticmethod
    def _row_to_offer(row: sqlite3.Row) -> NormalizedOffer:
        return NormalizedOffer(
            id=row["id"],
            provider=row["provider"],
            provider_offer_id=row["provider_offer_id"],
            title=row["title"],
            description=row["description"],
            price=row["price"],
            currency=row["currency"],
            unit_text=row["unit_text"],
            store_name=row["store_name"],
            store_chain=row["store_chain"],
            store_slug=row["store_slug"],
            store_id=row["store_id"],
            image_url=row["image_url"],
            valid_from=_from_iso(row["valid_from"]),
            valid_until=_from_iso(row["valid_until"]),
            source_url=row["source_url"],
            catalog_url=row["catalog_url"],
            page_number=row["page_number"],
            raw=json.loads(row["raw_json"]),
        )

    @staticmethod
    def _row_to_sync_run(row: sqlite3.Row) -> dict:
        return {
            "id": row["id"],
            "provider": row["provider"],
            "status": row["status"],
            "catalogs_discovered": row["catalogs_discovered"],
            "offers_fetched": row["offers_fetched"],
            "normalized_offers_saved": row["normalized_offers_saved"],
            "raw_payloads_persisted": row["raw_payloads_persisted"],
            "matches_created": row["matches_created"],
            "error_count": row["error_count"],
            "warnings": json.loads(row["warnings_json"] or "[]"),
            "errors": json.loads(row["errors_json"] or "[]"),
            "error": row["error"],
            "schema_drift_warning": row["schema_drift_warning"],
            "duration_ms": row["duration_ms"],
            "started_at": row["started_at"],
            "completed_at": row["completed_at"],
        }

    @staticmethod
    def _row_to_match_payload(row: sqlite3.Row) -> dict:
        return {
            "id": row["id"],
            "status": row["status"],
            "score": row["score"],
            "reasons": json.loads(row["reasons_json"]),
            "matched_keywords": json.loads(row["matched_keywords_json"]),
            "watched_product": {
                "id": row["watched_product_id"],
                "name": row["watched_product_name"],
                "max_price": row["watched_product_max_price"],
            },
            "offer": {
                "id": row["offer_id"],
                "provider": row["provider"],
                "provider_offer_id": row["provider_offer_id"],
                "title": row["title"],
                "description": row["description"],
                "price": row["price"],
                "currency": row["currency"],
                "unit_text": row["unit_text"],
                "store_name": row["store_name"],
                "store_chain": row["store_chain"],
                "store_slug": row["store_slug"],
                "store_id": row["store_id"],
                "image_url": row["image_url"],
                "valid_from": row["valid_from"],
                "valid_until": row["valid_until"],
                "source_url": row["source_url"],
                "catalog_url": row["catalog_url"],
                "page_number": row["page_number"],
                "raw": json.loads(row["raw_json"]),
            },
        }
