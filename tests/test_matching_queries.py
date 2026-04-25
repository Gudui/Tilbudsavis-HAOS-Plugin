from __future__ import annotations

from datetime import datetime, timezone

from app.db import Database
from app.models import NormalizedOffer, WatchedProduct
from app.providers.fixtures import MockFixtureProvider
from app.services.matching import build_matches, match_offer_to_watch
from app.services.queries import filter_matches, group_matches, sort_matches


NOW = datetime(2026, 4, 24, 12, 0, tzinfo=timezone.utc)


def _seed_matches(test_settings):
    database = Database(test_settings.database_path)
    database.initialize()

    watches = [
        WatchedProduct(id="watch-pepsi", name="Pepsi Max", keywords=["pepsi max", "1,5 l"], max_price=15.0),
        WatchedProduct(
            id="watch-kaffe",
            name="Kaffe",
            keywords=["kaffe", "formalede"],
            exclude_keywords=["instant"],
            max_price=55.0,
        ),
        WatchedProduct(id="watch-bleer", name="Bleer", keywords=["bleer", "pampers"], max_price=99.0),
    ]
    for watch in watches:
        database.upsert_watched_product(watch)

    offers = MockFixtureProvider(test_settings.fixture_dir).fetch_offers(watches)
    database.upsert_offers(offers)
    database.replace_matches(build_matches(watches, offers, now=NOW))
    return database.list_match_rows()


def test_matching_supports_include_exclude_max_price_and_store_filters():
    watch = WatchedProduct(
        id="watch-1",
        name="Kaffe",
        keywords=["kaffe"],
        exclude_keywords=["instant"],
        max_price=40.0,
        store_filters=["Netto"],
    )

    active_offer = NormalizedOffer(
        id="offer-1",
        provider="mock",
        title="Formalet kaffe 400 g",
        description="Kaffe til filter",
        price=35.0,
        currency="DKK",
        store_name="Netto Norrebro",
        store_chain="Netto",
        store_slug="netto",
        image_url=None,
        valid_from=datetime(2026, 4, 23, tzinfo=timezone.utc),
        valid_until=datetime(2026, 4, 26, tzinfo=timezone.utc),
        source_url=None,
        raw={},
    )
    blocked_offer = NormalizedOffer(
        id="offer-2",
        provider="mock",
        title="Instant kaffe",
        description="Kaffe til kop",
        price=35.0,
        currency="DKK",
        store_name="Netto Norrebro",
        store_chain="Netto",
        store_slug="netto",
        image_url=None,
        valid_from=datetime(2026, 4, 23, tzinfo=timezone.utc),
        valid_until=datetime(2026, 4, 26, tzinfo=timezone.utc),
        source_url=None,
        raw={},
    )
    wrong_store = NormalizedOffer(
        id="offer-3",
        provider="mock",
        title="Formalet kaffe 400 g",
        description="Kaffe til filter",
        price=35.0,
        currency="DKK",
        store_name="Bilka Fields",
        store_chain="Bilka",
        store_slug="bilka",
        image_url=None,
        valid_from=datetime(2026, 4, 23, tzinfo=timezone.utc),
        valid_until=datetime(2026, 4, 26, tzinfo=timezone.utc),
        source_url=None,
        raw={},
    )
    too_expensive = NormalizedOffer(
        id="offer-4",
        provider="mock",
        title="Formalet kaffe 400 g",
        description="Kaffe til filter",
        price=49.0,
        currency="DKK",
        store_name="Netto Norrebro",
        store_chain="Netto",
        store_slug="netto",
        image_url=None,
        valid_from=datetime(2026, 4, 23, tzinfo=timezone.utc),
        valid_until=datetime(2026, 4, 26, tzinfo=timezone.utc),
        source_url=None,
        raw={},
    )

    assert match_offer_to_watch(active_offer, watch, NOW) is not None
    assert match_offer_to_watch(blocked_offer, watch, NOW) is None
    assert match_offer_to_watch(wrong_store, watch, NOW) is None
    assert match_offer_to_watch(too_expensive, watch, NOW) is None


def test_filter_group_and_sort_queries(test_settings):
    rows = _seed_matches(test_settings)

    active = filter_matches(rows, status="active", now=NOW)
    upcoming = filter_matches(rows, status="upcoming", now=NOW)
    expired = filter_matches(rows, status="expired", now=NOW)
    expiring = filter_matches(rows, status="expiring", now=NOW)

    assert all(match["status"] == "active" for match in active)
    assert all(match["status"] == "upcoming" for match in upcoming)
    assert all(match["status"] == "expired" for match in expired)
    assert any(match["offer"]["store_slug"] == "rema-1000" for match in expiring)

    store_groups = group_matches(active, by="store")
    product_groups = group_matches(active, by="product")
    priced = sort_matches(active, by="price")
    expiring_order = sort_matches(active, by="expires")

    assert len(store_groups) == 4
    pepsi_group = next(group for group in product_groups if group["title"] == "Pepsi Max")
    assert pepsi_group["match_count"] == 2
    assert priced[0]["offer"]["price"] == 10.0
    assert expiring_order[0]["offer"]["id"] == "mock:pepsi-rema-no-image"
