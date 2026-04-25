from __future__ import annotations

import json

from app.providers.etilbudsavis import (
    EtilbudsavisProvider,
    extract_etilbudsavis_results,
    normalize_etilbudsavis_offer,
)
from app.providers.minetilbud import (
    CatalogReference,
    collect_offer_like_objects,
    discover_catalogs_from_homepage,
    extract_embedded_json_objects,
    normalize_minetilbud_offer,
)


def _load_json(path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _load_text(path):
    return path.read_text(encoding="utf-8")


def test_etilbudsavis_normalization_handles_missing_fields(test_settings):
    fixture_dir = test_settings.fixture_dir / "etilbudsavis"
    missing_price = normalize_etilbudsavis_offer(_load_json(fixture_dir / "response_missing_price.json")["results"][0])
    missing_image = normalize_etilbudsavis_offer(_load_json(fixture_dir / "response_missing_image.json")["results"][0])
    missing_store = normalize_etilbudsavis_offer(_load_json(fixture_dir / "response_missing_store.json")["results"][0])

    assert missing_price.price is None
    assert missing_image.image_url is None
    assert missing_store.store_name == "Unknown store"
    assert missing_store.store_slug == "unknown-store"


def test_etilbudsavis_partial_and_duplicate_payloads_are_tolerated(monkeypatch, test_settings):
    fixture_dir = test_settings.fixture_dir / "etilbudsavis"
    payloads = {
        "pepsi max": _load_json(fixture_dir / "response_duplicate_ids.json"),
        "kaffe": _load_json(fixture_dir / "response_malformed_partial.json"),
    }

    class FakeClient:
        def __init__(self, provider_name, settings):
            del provider_name, settings

        def get_json(self, url, *, params=None):
            del url
            return payloads[params["query"].casefold()]

        def close(self):
            return None

    monkeypatch.setattr("app.providers.etilbudsavis.ProviderHttpClient", FakeClient)
    provider = EtilbudsavisProvider(test_settings)
    result = provider.fetch_offers(
        [
            __import__("app.models", fromlist=["WatchedProduct"]).WatchedProduct(id="1", name="Pepsi Max", keywords=["pepsi max"]),
            __import__("app.models", fromlist=["WatchedProduct"]).WatchedProduct(id="2", name="Kaffe", keywords=["kaffe"]),
        ]
    )

    assert result.status == "degraded"
    assert result.provider_offers_fetched == 2
    assert len(result.offers) == 1
    assert result.schema_drift_warning is not None
    assert extract_etilbudsavis_results(_load_json(fixture_dir / "response_malformed_partial.json")) == []


def test_minetilbud_homepage_discovery_and_extraction(test_settings):
    fixture_dir = test_settings.fixture_dir / "minetilbud"
    homepage = _load_text(fixture_dir / "homepage.html")
    catalogs = discover_catalogs_from_homepage(homepage, base_url="https://minetilbud.dk")

    assert [catalog.store_slug for catalog in catalogs] == ["rema1000", "foetex", "lidl"]

    rema_html = _load_text(fixture_dir / "catalog_rema_assignment.html")
    foetex_html = _load_text(fixture_dir / "catalog_foetex_json_parse.html")
    rema_objects = extract_embedded_json_objects(rema_html)
    foetex_objects = extract_embedded_json_objects(foetex_html)

    assert rema_objects
    assert foetex_objects
    assert len(collect_offer_like_objects(rema_objects[0])) == 2

    catalog = CatalogReference(
        url="https://minetilbud.dk/katalog/rema1000/uge-17-rema-1000/",
        store_slug="rema1000",
        store_chain="REMA 1000",
        store_name="REMA 1000",
    )
    offer_like = collect_offer_like_objects(rema_objects[0])[0]
    normalized = normalize_minetilbud_offer(offer_like, catalog)

    assert normalized.provider == "minetilbud"
    assert normalized.store_slug == "rema-1000"
    assert normalized.catalog_url == catalog.url
    assert normalized.page_number == 3
