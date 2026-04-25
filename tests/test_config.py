from __future__ import annotations

import json

from app.config import load_settings, reset_settings_cache


def test_load_settings_prefers_env_over_options(monkeypatch, tmp_path):
    options_path = tmp_path / "options.json"
    options_path.write_text(
        json.dumps(
            {
                "provider": "etilbudsavis",
                "latitude": 56.0,
                "longitude": 10.0,
                "radius_meters": 12000,
                "locale": "da_DK",
                "sync_interval_minutes": 90,
                "max_results_per_query": 10,
                "request_timeout_seconds": 7,
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("OFFER_RADAR_OPTIONS_PATH", str(options_path))
    monkeypatch.setenv("OFFER_RADAR_PROVIDER", "mock")
    monkeypatch.setenv("OFFER_RADAR_DATA_DIR", str(tmp_path / "runtime-data"))

    reset_settings_cache()
    settings = load_settings()

    assert settings.provider == "mock"
    assert settings.latitude == 56.0
    assert settings.radius_meters == 12000
    assert settings.database_path == (tmp_path / "runtime-data" / "offer_radar.db").resolve()

