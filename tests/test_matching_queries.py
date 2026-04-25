from __future__ import annotations

from datetime import datetime, timezone

from app.db import Database
from app.models import NormalizedOffer, WatchedProduct
from app.services.matching import build_matches
from app.services.queries import filter_matches, group_matches
from app.services.store_normalization import canonicalize_chain_name, normalize_store_slug


NOW = datetime(2026, 4, 25, 12, 0, tzinfo=timezone.utc)


def test_store_normalization_aliases():
    assert canonicalize_chain_name("rema1000") == "REMA 1000"
    assert canonicalize_chain_name("rema-1000") == "REMA 1000"
    assert canonicalize_chain_name("foetex") == "føtex"
    assert normalize_store_slug("REMA 1000", "REMA 1000 Valby") == "rema-1000"


def test_store_grouping_combines_equivalent_chain_names(tmp_path):
    database = Database(tmp_path / "offer_radar.db")
    database.initialize()

    watch = WatchedProduct(id="watch-1", name="Pepsi Max", keywords=["pepsi max"])
    database.upsert_watched_product(watch)

    offers = [
        NormalizedOffer(
            id="etilbudsavis:1",
            provider="etilbudsavis",
            provider_offer_id="1",
            title="Pepsi Max 1,5 L",
            description=None,
            price=10.0,
            currency="DKK",
            unit_text="1,5 L",
            store_name="REMA 1000 Valby",
            store_chain="REMA 1000",
            store_slug="rema-1000",
            store_id="rema-1",
            image_url=None,
            valid_from=datetime(2026, 4, 24, tzinfo=timezone.utc),
            valid_until=datetime(2026, 4, 26, tzinfo=timezone.utc),
            source_url=None,
            catalog_url=None,
            page_number=3,
            raw={},
        ),
        NormalizedOffer(
            id="minetilbud:1",
            provider="minetilbud",
            provider_offer_id="1",
            title="Pepsi Max 1,5 L",
            description=None,
            price=11.0,
            currency="DKK",
            unit_text="1,5 L",
            store_name="REMA 1000",
            store_chain="REMA 1000",
            store_slug="rema-1000",
            store_id="rema1000",
            image_url=None,
            valid_from=datetime(2026, 4, 24, tzinfo=timezone.utc),
            valid_until=datetime(2026, 4, 26, tzinfo=timezone.utc),
            source_url=None,
            catalog_url=None,
            page_number=4,
            raw={},
        ),
    ]
    database.upsert_offers(offers)
    database.replace_matches(build_matches([watch], offers, now=NOW))

    active = filter_matches(database.list_match_rows(), status="active", now=NOW)
    store_groups = group_matches(active, by="store")
    product_groups = group_matches(active, by="product")

    assert len(store_groups) == 1
    assert store_groups[0]["match_count"] == 2
    assert product_groups[0]["match_count"] == 2

