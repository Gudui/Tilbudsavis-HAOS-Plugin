from __future__ import annotations

import hashlib
import time
from datetime import datetime, timezone
from typing import Any

from app.config import Settings
from app.models import NormalizedOffer, ProviderFetchResult, WatchedProduct
from app.providers.base import ProviderError
from app.providers.http import ProviderHttpClient
from app.services.store_normalization import canonicalize_chain_name, normalize_store_slug


def _parse_datetime(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    text = str(value).strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _parse_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    cleaned = str(value).strip().replace("kr.", "").replace("kr", "").replace(",", ".")
    digits = "".join(character for character in cleaned if character.isdigit() or character == ".")
    try:
        return float(digits) if digits else None
    except ValueError:
        return None


def _parse_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    if isinstance(value, int):
        return value
    digits = "".join(character for character in str(value) if character.isdigit())
    return int(digits) if digits else None


def _get_nested(data: dict[str, Any], *keys: str) -> Any:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _first_non_empty(*values: Any) -> Any:
    return next((value for value in values if value not in (None, "")), None)


def extract_etilbudsavis_results(payload: dict[str, Any]) -> list[dict[str, Any]]:
    candidate = _first_non_empty(
        payload.get("results"),
        payload.get("offers"),
        payload.get("items"),
        _get_nested(payload, "data", "results"),
        _get_nested(payload, "data", "offers"),
    )
    if isinstance(candidate, list):
        return [item for item in candidate if isinstance(item, dict)]
    return []


def normalize_etilbudsavis_offer(raw_offer: dict[str, Any], provider_name: str = "etilbudsavis") -> NormalizedOffer:
    store = raw_offer.get("store") or raw_offer.get("retailer") or {}
    images = raw_offer.get("images") or raw_offer.get("media") or {}
    validity = raw_offer.get("validity") or raw_offer.get("period") or {}
    links = raw_offer.get("links") or {}

    provider_offer_id = _first_non_empty(
        raw_offer.get("id"),
        raw_offer.get("offerId"),
        raw_offer.get("externalId"),
    )
    if not provider_offer_id:
        provider_offer_id = hashlib.sha1(repr(sorted(raw_offer.items())).encode("utf-8")).hexdigest()[:16]

    title = _first_non_empty(raw_offer.get("title"), raw_offer.get("heading"), raw_offer.get("name"), "Untitled offer")
    description = _first_non_empty(raw_offer.get("description"), raw_offer.get("subheading"), raw_offer.get("text"))
    price = _parse_float(
        _first_non_empty(
            raw_offer.get("price"),
            _get_nested(raw_offer, "pricing", "price"),
            _get_nested(raw_offer, "pricing", "current"),
            _get_nested(raw_offer, "priceInfo", "current"),
        )
    )
    currency = _first_non_empty(
        raw_offer.get("currency"),
        _get_nested(raw_offer, "pricing", "currency"),
        _get_nested(raw_offer, "priceInfo", "currency"),
        "DKK",
    )
    unit_text = _first_non_empty(
        raw_offer.get("unitText"),
        raw_offer.get("unit"),
        _get_nested(raw_offer, "priceInfo", "unit"),
    )
    raw_chain = _first_non_empty(store.get("chain"), store.get("chainName"), store.get("brand"), store.get("name"))
    store_chain = canonicalize_chain_name(str(raw_chain)) if raw_chain else None
    store_name = str(_first_non_empty(store.get("name"), store.get("displayName"), store_chain, "Unknown store"))
    store_id = _first_non_empty(store.get("id"), store.get("storeId"), store.get("retailerId"))
    image_url = _first_non_empty(
        images.get("primary"),
        images.get("medium"),
        raw_offer.get("image"),
        _get_nested(raw_offer, "image", "url"),
    )
    valid_from = _parse_datetime(_first_non_empty(validity.get("from"), raw_offer.get("validFrom")))
    valid_until = _parse_datetime(_first_non_empty(validity.get("until"), raw_offer.get("validUntil")))
    source_url = _first_non_empty(links.get("web"), raw_offer.get("sourceUrl"), raw_offer.get("url"))
    catalog_url = _first_non_empty(links.get("catalog"), raw_offer.get("catalogUrl"))
    page_number = _parse_int(_first_non_empty(raw_offer.get("pageNumber"), raw_offer.get("page")))

    return NormalizedOffer(
        id=f"{provider_name}:{provider_offer_id}",
        provider=provider_name,
        provider_offer_id=str(provider_offer_id),
        title=str(title),
        description=str(description) if description else None,
        price=price,
        currency=str(currency) if currency else None,
        unit_text=str(unit_text) if unit_text else None,
        store_name=store_name,
        store_chain=store_chain,
        store_slug=normalize_store_slug(store_chain, store_name),
        store_id=str(store_id) if store_id else None,
        image_url=str(image_url) if image_url else None,
        valid_from=valid_from,
        valid_until=valid_until,
        source_url=str(source_url) if source_url else None,
        catalog_url=str(catalog_url) if catalog_url else None,
        page_number=page_number,
        raw=raw_offer,
    )


class EtilbudsavisProvider:
    provider_name = "etilbudsavis"

    def __init__(self, settings: Settings):
        self.settings = settings

    def fetch_offers(self, watched_products: list[WatchedProduct]) -> ProviderFetchResult:
        started = time.perf_counter()
        if not watched_products:
            return ProviderFetchResult(provider=self.provider_name, status="ok")

        query_terms = self._build_query_terms(watched_products)
        client = ProviderHttpClient(self.provider_name, self.settings)
        offers: dict[str, NormalizedOffer] = {}
        errors: list[str] = []
        warnings: list[str] = []
        provider_offers_fetched = 0
        schema_drift_warning: str | None = None
        try:
            for term in query_terms:
                params = {
                    "query": term,
                    "locale": self.settings.etilbudsavis_locale,
                    "latitude": self.settings.latitude,
                    "longitude": self.settings.longitude,
                    "radius": self.settings.etilbudsavis_radius_meters,
                    "limit": self.settings.etilbudsavis_max_results_per_query,
                }
                try:
                    payload = client.get_json(self.settings.etilbudsavis_request_url, params=params)
                except ProviderError as exc:
                    errors.extend(exc.errors)
                    if exc.schema_drift_warning and not schema_drift_warning:
                        schema_drift_warning = exc.schema_drift_warning
                    continue

                raw_results = extract_etilbudsavis_results(payload)
                if not raw_results:
                    warning = f"No extractable results for eTilbudsavis query '{term}'."
                    warnings.append(warning)
                    schema_drift_warning = schema_drift_warning or warning
                    continue

                provider_offers_fetched += len(raw_results)
                for raw_offer in raw_results:
                    normalized = normalize_etilbudsavis_offer(raw_offer, provider_name=self.provider_name)
                    offers[normalized.id] = normalized
        finally:
            client.close()

        status = "ok"
        if errors and offers:
            status = "degraded"
        elif errors and not offers:
            status = "failed"
        elif warnings:
            status = "degraded"

        result = ProviderFetchResult(
            provider=self.provider_name,
            offers=list(offers.values()),
            status=status,
            provider_offers_fetched=provider_offers_fetched,
            raw_payloads_persisted=len(offers),
            error_count=len(errors),
            warnings=warnings,
            errors=errors,
            last_error=errors[-1] if errors else None,
            schema_drift_warning=schema_drift_warning,
            duration_ms=int((time.perf_counter() - started) * 1000),
        )
        return result

    def _build_query_terms(self, watched_products: list[WatchedProduct]) -> list[str]:
        seen: set[str] = set()
        terms: list[str] = []
        for watch in watched_products:
            for term in [watch.name, *watch.keywords]:
                normalized = term.strip()
                key = normalized.casefold()
                if normalized and key not in seen:
                    seen.add(key)
                    terms.append(normalized)
        return terms[: self.settings.etilbudsavis_max_results_per_query]

