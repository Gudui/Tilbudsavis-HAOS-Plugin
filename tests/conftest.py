from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def make_settings(tmp_path: Path, providers: list[str] | None = None) -> Settings:
    enabled = providers or ["mock"]
    return Settings(
        providers=enabled,
        data_dir=tmp_path,
        database_path=tmp_path / "offer_radar.db",
        options_path=tmp_path / "options.json",
        latitude=55.6761,
        longitude=12.5683,
        radius_meters=25000,
        locale="da_DK",
        sync_interval_minutes=0,
        max_results_per_query=24,
        provider_timeout_seconds=15,
        provider_rate_limit_seconds=0,
        provider_max_retries=0,
        provider_user_agent="OfferRadarTest/1.0",
        live_provider_tests=False,
        etilbudsavis_base_url="https://api.etilbudsavis.dk",
        etilbudsavis_search_url="https://api.etilbudsavis.dk/v2/offers/search",
        etilbudsavis_locale="da_DK",
        etilbudsavis_radius_meters=10000,
        etilbudsavis_max_results_per_query=10,
        minetilbud_base_url="https://minetilbud.dk",
        minetilbud_max_catalogs_per_sync=50,
        minetilbud_store_filters=[],
        clear_seed_data=False,
    )


@pytest.fixture
def test_settings(tmp_path: Path) -> Settings:
    return make_settings(tmp_path)


@pytest.fixture
def client(test_settings: Settings):
    app = create_app(test_settings)
    with TestClient(app) as test_client:
        yield test_client

