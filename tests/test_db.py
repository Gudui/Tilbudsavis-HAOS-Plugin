from __future__ import annotations

import sqlite3

from app.db import Database


def test_database_initializes_schema(tmp_path):
    db_path = tmp_path / "offer_radar.db"
    database = Database(db_path)

    database.initialize()

    assert db_path.exists()

    with sqlite3.connect(db_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }

    assert {"watched_products", "offers", "matches", "sync_runs"}.issubset(tables)
