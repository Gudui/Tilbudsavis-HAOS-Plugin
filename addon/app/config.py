from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any


def _coerce_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _coerce_float(value: Any, default: float) -> float:
    if value in (None, ""):
        return default
    return float(value)


def _coerce_int(value: Any, default: int) -> int:
    if value in (None, ""):
        return default
    return int(value)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return data if isinstance(data, dict) else {}


@dataclass(slots=True)
class Settings:
    provider: str
    data_dir: Path
    database_path: Path
    options_path: Path
    latitude: float
    longitude: float
    radius_meters: int
    locale: str
    sync_interval_minutes: int
    max_results_per_query: int
    request_timeout_seconds: int
    etilbudsavis_search_url: str | None
    clear_seed_data: bool

    @property
    def fixture_dir(self) -> Path:
        return Path(__file__).resolve().parent / "providers" / "fixtures"


def load_settings() -> Settings:
    options_path = Path(os.getenv("OFFER_RADAR_OPTIONS_PATH", "/data/options.json"))
    options = _read_json(options_path)

    data_dir = Path(os.getenv("OFFER_RADAR_DATA_DIR", options.get("data_dir") or "data")).resolve()

    def option(name: str, env_name: str, default: Any) -> Any:
        if env_name in os.environ:
            return os.environ[env_name]
        return options.get(name, default)

    provider = str(option("provider", "OFFER_RADAR_PROVIDER", "mock")).strip() or "mock"
    latitude = _coerce_float(option("latitude", "OFFER_RADAR_LATITUDE", 55.6761), 55.6761)
    longitude = _coerce_float(option("longitude", "OFFER_RADAR_LONGITUDE", 12.5683), 12.5683)
    radius_meters = _coerce_int(option("radius_meters", "OFFER_RADAR_RADIUS_METERS", 25000), 25000)
    locale = str(option("locale", "OFFER_RADAR_LOCALE", "da_DK"))
    sync_interval_minutes = _coerce_int(
        option("sync_interval_minutes", "OFFER_RADAR_SYNC_INTERVAL_MINUTES", 0),
        0,
    )
    max_results_per_query = _coerce_int(
        option("max_results_per_query", "OFFER_RADAR_MAX_RESULTS_PER_QUERY", 24),
        24,
    )
    request_timeout_seconds = _coerce_int(
        option("request_timeout_seconds", "OFFER_RADAR_REQUEST_TIMEOUT_SECONDS", 12),
        12,
    )
    etilbudsavis_search_url = str(
        option("etilbudsavis_search_url", "OFFER_RADAR_ETILBUDSAVIS_SEARCH_URL", "")
    ).strip() or None
    clear_seed_data = _coerce_bool(os.getenv("OFFER_RADAR_CLEAR_SEED_DATA"), False)

    return Settings(
        provider=provider,
        data_dir=data_dir,
        database_path=data_dir / "offer_radar.db",
        options_path=options_path,
        latitude=latitude,
        longitude=longitude,
        radius_meters=radius_meters,
        locale=locale,
        sync_interval_minutes=sync_interval_minutes,
        max_results_per_query=max_results_per_query,
        request_timeout_seconds=request_timeout_seconds,
        etilbudsavis_search_url=etilbudsavis_search_url,
        clear_seed_data=clear_seed_data,
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return load_settings()


def reset_settings_cache() -> None:
    get_settings.cache_clear()
