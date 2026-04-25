from __future__ import annotations

import json

from app.config import load_settings, reset_settings_cache


def test_load_settings_prefers_env_over_options(monkeypatch, tmp_path):
    options_path = tmp_path / "options.json"
    options_path.write_text(
        json.dumps(
            {
                "providers": ["mock", "minetilbud"],
                "provider_timeout_seconds": 9,
                "minetilbud_store_filters": ["rema1000"]
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("OFFER_RADAR_OPTIONS_PATH", str(options_path))
    monkeypatch.setenv("OFFER_RADAR_PROVIDERS", "etilbudsavis,mock")
    monkeypatch.setenv("OFFER_RADAR_DATA_DIR", str(tmp_path / "runtime-data"))
    monkeypatch.setenv("MINETILBUD_STORE_FILTERS", "foetex,lidl")

    reset_settings_cache()
    settings = load_settings()

    assert settings.providers == ["etilbudsavis", "mock"]
    assert settings.provider_timeout_seconds == 9
    assert settings.minetilbud_store_filters == ["foetex", "lidl"]
    assert settings.database_path == (tmp_path / "runtime-data" / "offer_radar.db").resolve()

