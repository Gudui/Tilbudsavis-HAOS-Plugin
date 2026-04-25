from __future__ import annotations


def test_root_and_health_endpoints_render(client):
    root = client.get("/")
    health = client.get("/health")

    assert root.status_code == 200
    assert "Offer Radar" in root.text
    assert health.status_code == 200
    assert health.json()["status"] == "ok"


def test_sync_and_match_views_work_with_mock_provider(client):
    sync = client.post("/api/sync")
    assert sync.status_code == 200
    assert sync.json()["status"] == "ok"
    assert sync.json()["offers_fetched"] == 6

    active = client.get("/api/matches?status=active")
    upcoming = client.get("/api/matches?status=upcoming")
    grouped_store = client.get("/api/matches/grouped?by=store")
    grouped_product = client.get("/api/matches/grouped?by=product")
    sorted_price = client.get("/api/matches/sorted?by=price")
    sorted_expires = client.get("/api/matches/sorted?by=expires")
    stores = client.get("/api/stores")

    assert active.status_code == 200
    assert all(match["status"] == "active" for match in active.json()["matches"])
    assert all(match["status"] == "upcoming" for match in upcoming.json()["matches"])
    assert grouped_store.json()["groups"]
    assert grouped_product.json()["groups"]
    assert sorted_price.json()["matches"][0]["offer"]["price"] == 10.0
    assert sorted_expires.json()["matches"][0]["offer"]["id"] == "mock:pepsi-rema-no-image"
    assert stores.json()["stores"]
