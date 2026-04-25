from __future__ import annotations

import json

from app.providers.etilbudsavis import normalize_etilbudsavis_offer
from app.providers.fixtures import MockFixtureProvider


def _load_fixture(path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)["results"][0]


def test_mock_provider_loads_all_fixture_offers(test_settings):
    provider = MockFixtureProvider(test_settings.fixture_dir)

    offers = provider.fetch_offers([])

    assert len(offers) == 6
    assert any(offer.store_name == "Unknown store" for offer in offers)
    assert any(offer.image_url is None for offer in offers)
    assert any(offer.price is None for offer in offers)


def test_etilbudsavis_normalization_tolerates_missing_fields(test_settings):
    fixture_dir = test_settings.fixture_dir

    missing_store = normalize_etilbudsavis_offer(_load_fixture(fixture_dir / "etilbudsavis_missing_store.json"))
    missing_price = normalize_etilbudsavis_offer(_load_fixture(fixture_dir / "etilbudsavis_missing_price.json"))
    missing_image = normalize_etilbudsavis_offer(_load_fixture(fixture_dir / "etilbudsavis_missing_image.json"))

    assert missing_store.store_name == "Unknown store"
    assert missing_store.store_slug == "unknown-store"
    assert missing_price.price is None
    assert missing_price.currency == "DKK"
    assert missing_image.image_url is None

