from __future__ import annotations

import sqlite3

from app.db import Database


def test_database_initializes_schema_with_provider_columns(tmp_path):
    db_path = tmp_path / "offer_radar.db"
    database = Database(db_path)

    database.initialize()

    assert db_path.exists()

    with sqlite3.connect(db_path) as connection:
        offer_columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(offers)").fetchall()
        }
        sync_columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(sync_runs)").fetchall()
        }

    assert {"provider_offer_id", "unit_text", "store_id", "catalog_url", "page_number"}.issubset(offer_columns)
    assert {"catalogs_discovered", "normalized_offers_saved", "raw_payloads_persisted", "schema_drift_warning"}.issubset(sync_columns)

