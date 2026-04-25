from __future__ import annotations

import json
from pathlib import Path

from app.models import NormalizedOffer, WatchedProduct
from app.providers.etilbudsavis import normalize_etilbudsavis_offer


class MockFixtureProvider:
    provider_name = "mock"

    def __init__(self, fixture_dir: Path):
        self.fixture_dir = fixture_dir

    def fetch_offers(self, watched_products: list[WatchedProduct]) -> list[NormalizedOffer]:
        del watched_products
        offers: list[NormalizedOffer] = []
        for path in sorted(self.fixture_dir.glob("*.json")):
            with path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
            for raw_offer in payload.get("results", []):
                offers.append(normalize_etilbudsavis_offer(raw_offer, provider_name="mock"))
        return offers

