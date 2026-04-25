from __future__ import annotations

from app.db import Database
from app.models import ProviderFetchResult
from app.providers.base import ProviderError
from app.services.sync import list_provider_health, run_sync
from tests.conftest import make_settings


class FailingProvider:
    provider_name = "failing"

    def fetch_offers(self, watched_products):
        del watched_products
        raise ProviderError("Simulated provider failure", status="failed")


def test_multi_provider_sync_survives_one_failure(monkeypatch, tmp_path):
    settings = make_settings(tmp_path, providers=["mock", "failing"])
    database = Database(settings.database_path)
    database.initialize()
    database.maybe_seed_watched_products()

    monkeypatch.setitem(
        __import__("app.providers.registry", fromlist=["PROVIDER_FACTORIES"]).PROVIDER_FACTORIES,
        "failing",
        lambda configured_settings: FailingProvider(),
    )

    result = run_sync(database, settings)
    snapshots = list_provider_health(database, settings)

    assert result["status"] == "degraded"
    assert result["matches_created_total"] > 0
    assert any(run["provider"] == "failing" and run["status"] == "failed" for run in result["providers"])
    assert any(snapshot["provider"] == "mock" and snapshot["raw_payload_count"] > 0 for snapshot in snapshots)
    assert any(snapshot["provider"] == "failing" and snapshot["status"] == "failed" for snapshot in snapshots)

