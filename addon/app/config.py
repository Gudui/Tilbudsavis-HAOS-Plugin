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


def _coerce_csv_list(value: Any, default: list[str] | None = None) -> list[str]:
    if value in (None, ""):
        return list(default or [])
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [part.strip() for part in str(value).split(",") if part.strip()]


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return data if isinstance(data, dict) else {}


@dataclass(slots=True)
class Settings:
    providers: list[str]
    data_dir: Path
    database_path: Path
    options_path: Path
    latitude: float
    longitude: float
    radius_meters: int
    locale: str
    sync_interval_minutes: int
    max_results_per_query: int
    provider_timeout_seconds: int
    provider_rate_limit_seconds: float
    provider_max_retries: int
    provider_user_agent: str
    live_provider_tests: bool
    etilbudsavis_base_url: str
    etilbudsavis_search_url: str | None
    etilbudsavis_locale: str
    etilbudsavis_radius_meters: int
    etilbudsavis_max_results_per_query: int
    minetilbud_base_url: str
    minetilbud_max_catalogs_per_sync: int
    minetilbud_store_filters: list[str]
    clear_seed_data: bool

    @property
    def fixture_dir(self) -> Path:
        return Path(__file__).resolve().parent / "providers" / "fixtures"

    @property
    def provider(self) -> str:
        return self.providers[0] if self.providers else "mock"

    @property
    def etilbudsavis_request_url(self) -> str:
        if self.etilbudsavis_search_url:
            return self.etilbudsavis_search_url
        return f"{self.etilbudsavis_base_url.rstrip('/')}/v2/offers/search"


def load_settings() -> Settings:
    options_path = Path(os.getenv("OFFER_RADAR_OPTIONS_PATH", "/data/options.json"))
    options = _read_json(options_path)

    data_dir = Path(os.getenv("OFFER_RADAR_DATA_DIR", options.get("data_dir") or "data")).resolve()

    def option(name: str, env_name: str, default: Any) -> Any:
        if env_name in os.environ:
            return os.environ[env_name]
        return options.get(name, default)

    legacy_provider = str(option("provider", "OFFER_RADAR_PROVIDER", "mock")).strip() or "mock"
    providers = _coerce_csv_list(option("providers", "OFFER_RADAR_PROVIDERS", [legacy_provider]), [legacy_provider])

    latitude = _coerce_float(option("latitude", "OFFER_RADAR_LATITUDE", 55.6761), 55.6761)
    longitude = _coerce_float(option("longitude", "OFFER_RADAR_LONGITUDE", 12.5683), 12.5683)
    radius_meters = _coerce_int(option("radius_meters", "OFFER_RADAR_RADIUS_METERS", 25000), 25000)
    locale = str(option("locale", "OFFER_RADAR_LOCALE", "da_DK"))
    sync_interval_minutes = _coerce_int(option("sync_interval_minutes", "OFFER_RADAR_SYNC_INTERVAL_MINUTES", 0), 0)
    max_results_per_query = _coerce_int(
        option("max_results_per_query", "OFFER_RADAR_MAX_RESULTS_PER_QUERY", 24),
        24,
    )
    provider_timeout_seconds = _coerce_int(
        option("provider_timeout_seconds", "OFFER_RADAR_PROVIDER_TIMEOUT_SECONDS", 15),
        15,
    )
    provider_rate_limit_seconds = _coerce_float(
        option("provider_rate_limit_seconds", "OFFER_RADAR_PROVIDER_RATE_LIMIT_SECONDS", 2),
        2.0,
    )
    provider_max_retries = _coerce_int(
        option("provider_max_retries", "OFFER_RADAR_PROVIDER_MAX_RETRIES", 2),
        2,
    )
    provider_user_agent = str(
        option(
            "provider_user_agent",
            "OFFER_RADAR_PROVIDER_USER_AGENT",
            "OfferRadar/0.2 (+https://github.com/Gudui/Tilbudsavis-HAOS-Plugin; personal-use local add-on)",
        )
    ).strip()
    live_provider_tests = _coerce_bool(
        option("live_provider_tests", "OFFER_RADAR_LIVE_PROVIDER_TESTS", False),
        False,
    )

    etilbudsavis_base_url = str(
        option("etilbudsavis_base_url", "ETILBUDSAVIS_BASE_URL", "https://api.etilbudsavis.dk")
    ).strip()
    etilbudsavis_search_url = str(
        option("etilbudsavis_search_url", "ETILBUDSAVIS_SEARCH_URL", "")
    ).strip() or None
    etilbudsavis_locale = str(option("etilbudsavis_locale", "ETILBUDSAVIS_LOCALE", locale))
    etilbudsavis_radius_meters = _coerce_int(
        option("etilbudsavis_radius_meters", "ETILBUDSAVIS_RADIUS_METERS", radius_meters),
        radius_meters,
    )
    etilbudsavis_max_results_per_query = _coerce_int(
        option("etilbudsavis_max_results_per_query", "ETILBUDSAVIS_MAX_RESULTS_PER_QUERY", max_results_per_query),
        max_results_per_query,
    )

    minetilbud_base_url = str(
        option("minetilbud_base_url", "MINETILBUD_BASE_URL", "https://minetilbud.dk")
    ).strip()
    minetilbud_max_catalogs_per_sync = _coerce_int(
        option("minetilbud_max_catalogs_per_sync", "MINETILBUD_MAX_CATALOGS_PER_SYNC", 50),
        50,
    )
    minetilbud_store_filters = _coerce_csv_list(
        option("minetilbud_store_filters", "MINETILBUD_STORE_FILTERS", []),
        [],
    )

    clear_seed_data = _coerce_bool(os.getenv("OFFER_RADAR_CLEAR_SEED_DATA"), False)

    return Settings(
        providers=providers or ["mock"],
        data_dir=data_dir,
        database_path=data_dir / "offer_radar.db",
        options_path=options_path,
        latitude=latitude,
        longitude=longitude,
        radius_meters=radius_meters,
        locale=locale,
        sync_interval_minutes=sync_interval_minutes,
        max_results_per_query=max_results_per_query,
        provider_timeout_seconds=provider_timeout_seconds,
        provider_rate_limit_seconds=provider_rate_limit_seconds,
        provider_max_retries=provider_max_retries,
        provider_user_agent=provider_user_agent,
        live_provider_tests=live_provider_tests,
        etilbudsavis_base_url=etilbudsavis_base_url,
        etilbudsavis_search_url=etilbudsavis_search_url,
        etilbudsavis_locale=etilbudsavis_locale,
        etilbudsavis_radius_meters=etilbudsavis_radius_meters,
        etilbudsavis_max_results_per_query=etilbudsavis_max_results_per_query,
        minetilbud_base_url=minetilbud_base_url,
        minetilbud_max_catalogs_per_sync=minetilbud_max_catalogs_per_sync,
        minetilbud_store_filters=minetilbud_store_filters,
        clear_seed_data=clear_seed_data,
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return load_settings()


def reset_settings_cache() -> None:
    get_settings.cache_clear()

