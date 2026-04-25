from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture
def test_settings(tmp_path: Path) -> Settings:
    return Settings(
        provider="mock",
        data_dir=tmp_path,
        database_path=tmp_path / "offer_radar.db",
        options_path=tmp_path / "options.json",
        latitude=55.6761,
        longitude=12.5683,
        radius_meters=25000,
        locale="da_DK",
        sync_interval_minutes=0,
        max_results_per_query=24,
        request_timeout_seconds=12,
        etilbudsavis_search_url=None,
        clear_seed_data=False,
    )


@pytest.fixture
def client(test_settings: Settings):
    app = create_app(test_settings)
    with TestClient(app) as test_client:
        yield test_client

