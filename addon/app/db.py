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
                    title TEXT NOT NULL,
                    description TEXT,
                    price REAL,
                    currency TEXT,
                    store_name TEXT NOT NULL,
                    store_chain TEXT,
                    store_slug TEXT NOT NULL,
                    image_url TEXT,
                    valid_from TEXT,
                    valid_until TEXT,
                    source_url TEXT,
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
                    offers_fetched INTEGER NOT NULL DEFAULT 0,
                    matches_created INTEGER NOT NULL DEFAULT 0,
                    error TEXT,
                    started_at TEXT NOT NULL,
                    completed_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_matches_status ON matches(status);
                CREATE INDEX IF NOT EXISTS idx_matches_watch ON matches(watched_product_id);
                CREATE INDEX IF NOT EXISTS idx_offers_store_slug ON offers(store_slug);
                """
            )

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
                offer.title,
                offer.description,
                offer.price,
                offer.currency,
                offer.store_name,
                offer.store_chain,
                offer.store_slug,
                offer.image_url,
                _to_iso(offer.valid_from),
                _to_iso(offer.valid_until),
                offer.source_url,
                json.dumps(offer.raw),
                _utc_now(),
            )
            for offer in offers
        ]
        with self.connect() as conn:
            conn.executemany(
                """
                INSERT INTO offers (
                    id, provider, title, description, price, currency, store_name, store_chain, store_slug,
                    image_url, valid_from, valid_until, source_url, raw_json, normalized_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    provider = excluded.provider,
                    title = excluded.title,
                    description = excluded.description,
                    price = excluded.price,
                    currency = excluded.currency,
                    store_name = excluded.store_name,
                    store_chain = excluded.store_chain,
                    store_slug = excluded.store_slug,
                    image_url = excluded.image_url,
                    valid_from = excluded.valid_from,
                    valid_until = excluded.valid_until,
                    source_url = excluded.source_url,
                    raw_json = excluded.raw_json,
                    normalized_at = excluded.normalized_at
                """,
                payload,
            )

    def list_offers(self) -> list[NormalizedOffer]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, provider, title, description, price, currency, store_name, store_chain, store_slug,
                       image_url, valid_from, valid_until, source_url, raw_json
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
        offers_fetched: int,
        matches_created: int,
        error: str | None = None,
    ) -> dict[str, str | int | None]:
        sync_id = str(uuid.uuid4())
        started_at = _utc_now()
        completed_at = _utc_now()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO sync_runs (
                    id, provider, status, offers_fetched, matches_created, error, started_at, completed_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sync_id,
                    provider,
                    status,
                    offers_fetched,
                    matches_created,
                    error,
                    started_at,
                    completed_at,
                ),
            )
        return {
            "id": sync_id,
            "provider": provider,
            "status": status,
            "offers_fetched": offers_fetched,
            "matches_created": matches_created,
            "error": error,
            "started_at": started_at,
            "completed_at": completed_at,
        }

    def get_last_sync_run(self) -> dict[str, str | int | None] | None:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT id, provider, status, offers_fetched, matches_created, error, started_at, completed_at
                FROM sync_runs
                ORDER BY completed_at DESC
                LIMIT 1
                """
            ).fetchone()
        return dict(row) if row else None

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
                    o.title,
                    o.description,
                    o.price,
                    o.currency,
                    o.store_name,
                    o.store_chain,
                    o.store_slug,
                    o.image_url,
                    o.valid_from,
                    o.valid_until,
                    o.source_url,
                    o.raw_json
                FROM matches m
                JOIN watched_products w ON w.id = m.watched_product_id
                JOIN offers o ON o.id = m.offer_id
                ORDER BY m.score DESC, o.title COLLATE NOCASE
                """
            ).fetchall()
        return [self._row_to_match_payload(row) for row in rows]

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
            title=row["title"],
            description=row["description"],
            price=row["price"],
            currency=row["currency"],
            store_name=row["store_name"],
            store_chain=row["store_chain"],
            store_slug=row["store_slug"],
            image_url=row["image_url"],
            valid_from=_from_iso(row["valid_from"]),
            valid_until=_from_iso(row["valid_until"]),
            source_url=row["source_url"],
            raw=json.loads(row["raw_json"]),
        )

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
                "title": row["title"],
                "description": row["description"],
                "price": row["price"],
                "currency": row["currency"],
                "store_name": row["store_name"],
                "store_chain": row["store_chain"],
                "store_slug": row["store_slug"],
                "image_url": row["image_url"],
                "valid_from": row["valid_from"],
                "valid_until": row["valid_until"],
                "source_url": row["source_url"],
                "raw": json.loads(row["raw_json"]),
            },
        }

