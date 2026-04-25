from __future__ import annotations

import os

import pytest

from app.config import load_settings
from app.models import ProviderFetchResult, WatchedProduct
from app.providers.registry import build_provider


pytestmark = pytest.mark.skipif(
    os.getenv("OFFER_RADAR_LIVE_PROVIDER_TESTS", "false").lower() != "true",
    reason="Live provider smoke tests are disabled by default.",
)


def _live_watch() -> list[WatchedProduct]:
    return [
        WatchedProduct(
            id="live-kaffe",
            name="Kaffe",
            keywords=["kaffe"],
            exclude_keywords=["instant"],
            enabled=True,
        )
    ]


@pytest.mark.parametrize("provider_name", ["etilbudsavis", "minetilbud"])
def test_live_provider_smoke(provider_name: str):
    settings = load_settings()
    provider = build_provider(provider_name, settings)

    result = provider.fetch_offers(_live_watch())

    assert isinstance(result, ProviderFetchResult)
    assert result.provider == provider_name
    assert result.status in {"ok", "degraded", "failed"}
    assert result.duration_ms >= 0
