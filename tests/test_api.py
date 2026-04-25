from __future__ import annotations


def test_root_health_and_provider_endpoints_render(client):
    root = client.get("/")
    health = client.get("/health")
    providers = client.get("/api/providers")

    assert root.status_code == 200
    assert "Offer Radar" in root.text
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert providers.status_code == 200
    assert providers.json()["providers"]


def test_sync_and_provider_diagnostics_work(client):
    sync = client.post("/api/sync")
    assert sync.status_code == 200
    assert sync.json()["status"] == "ok"
    assert sync.json()["offers_fetched_total"] >= 4

    provider_runs = client.get("/api/sync-runs")
    provider_health = client.get("/api/providers/mock/health")
    dashboard = client.get("/api/dashboard")

    assert provider_runs.status_code == 200
    assert provider_runs.json()["sync_runs"]
    assert provider_health.status_code == 200
    assert provider_health.json()["status"] == "ok"
    assert dashboard.status_code == 200
    assert dashboard.json()["providers"]
