from __future__ import annotations

import hashlib
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode

import httpx

from app.config import Settings
from app.models import NormalizedOffer, WatchedProduct
from app.providers.base import ProviderError


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    text = str(value).strip()
    if not text:
        return None
    normalized = text.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _parse_price(raw_offer: dict[str, Any]) -> tuple[float | None, str | None]:
    price_sources = [
        raw_offer.get("price"),
        raw_offer.get("pricing", {}).get("price"),
        raw_offer.get("pricing", {}).get("current"),
        raw_offer.get("priceInfo", {}).get("current"),
    ]
    currency_sources = [
        raw_offer.get("currency"),
        raw_offer.get("pricing", {}).get("currency"),
        raw_offer.get("priceInfo", {}).get("currency"),
    ]
    price = next((value for value in price_sources if value not in (None, "")), None)
    currency = next((value for value in currency_sources if value not in (None, "")), None)
    return (float(price), str(currency) if currency else None) if price is not None else (None, str(currency) if currency else None)


def slugify_store(value: str | None) -> str:
    text = (value or "unknown-store").strip().casefold()
    cleaned = []
    for character in text:
        if character.isalnum():
            cleaned.append(character)
        elif character in {" ", "-", "_", "/"}:
            cleaned.append("-")
    slug = "".join(cleaned).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug or "unknown-store"


def normalize_etilbudsavis_offer(raw_offer: dict[str, Any], provider_name: str = "etilbudsavis") -> NormalizedOffer:
    store = raw_offer.get("store") or raw_offer.get("retailer") or {}
    images = raw_offer.get("images") or {}
    validity = raw_offer.get("validity") or {}
    links = raw_offer.get("links") or {}

    external_id = raw_offer.get("id") or raw_offer.get("offerId")
    if not external_id:
        external_id = hashlib.sha1(repr(sorted(raw_offer.items())).encode("utf-8")).hexdigest()[:16]

    title = raw_offer.get("title") or raw_offer.get("heading") or "Untitled offer"
    description = raw_offer.get("description") or raw_offer.get("subheading")
    price, currency = _parse_price(raw_offer)
    store_name = store.get("name") or store.get("displayName") or "Unknown store"
    store_chain = store.get("chain") or store.get("chainName") or store.get("brand")
    image_url = images.get("primary") or images.get("medium") or raw_offer.get("image")
    valid_from = _parse_datetime(validity.get("from") or raw_offer.get("validFrom"))
    valid_until = _parse_datetime(validity.get("until") or raw_offer.get("validUntil"))
    source_url = links.get("web") or raw_offer.get("sourceUrl") or raw_offer.get("url")

    canonical_id = f"{provider_name}:{external_id}"
    return NormalizedOffer(
        id=canonical_id,
        provider=provider_name,
        title=str(title),
        description=str(description) if description else None,
        price=price,
        currency=currency,
        store_name=str(store_name),
        store_chain=str(store_chain) if store_chain else None,
        store_slug=slugify_store(str(store_chain or store_name)),
        image_url=str(image_url) if image_url else None,
        valid_from=valid_from,
        valid_until=valid_until,
        source_url=str(source_url) if source_url else None,
        raw=raw_offer,
    )


class EtilbudsavisProvider:
    provider_name = "etilbudsavis"

    def __init__(self, settings: Settings):
        self.settings = settings
        self._last_request_started = 0.0

    def fetch_offers(self, watched_products: list[WatchedProduct]) -> list[NormalizedOffer]:
        if not self.settings.etilbudsavis_search_url:
            raise ProviderError(
                "The unofficial eTilbudsavis adapter is enabled, but OFFER_RADAR_ETILBUDSAVIS_SEARCH_URL is not configured."
            )
        if not watched_products:
            return []

        offers: dict[str, NormalizedOffer] = {}
        query_terms = self._build_query_terms(watched_products)
        headers = {
            "User-Agent": "OfferRadar/0.1 (+https://github.com/example/offer-radar; personal-use local add-on)",
            "Accept": "application/json",
        }
        timeout = httpx.Timeout(float(self.settings.request_timeout_seconds))

        with httpx.Client(timeout=timeout, headers=headers) as client:
            for term in query_terms:
                self._respect_rate_limit()
                try:
                    response = client.get(
                        self.settings.etilbudsavis_search_url,
                        params={
                            "query": term,
                            "latitude": self.settings.latitude,
                            "longitude": self.settings.longitude,
                            "radius": self.settings.radius_meters,
                            "locale": self.settings.locale,
                            "limit": self.settings.max_results_per_query,
                        },
                    )
                    response.raise_for_status()
                except httpx.HTTPError as exc:
                    raise ProviderError(
                        f"Unofficial eTilbudsavis request failed for query '{term}': {exc}"
                    ) from exc

                payload = response.json()
                for raw_offer in payload.get("results", []):
                    normalized = normalize_etilbudsavis_offer(raw_offer)
                    offers[normalized.id] = normalized
        return list(offers.values())

    def _build_query_terms(self, watched_products: list[WatchedProduct]) -> list[str]:
        terms: list[str] = []
        seen: set[str] = set()
        for product in watched_products:
            for term in [product.name, *product.keywords]:
                normalized = term.strip()
                if normalized and normalized.casefold() not in seen:
                    seen.add(normalized.casefold())
                    terms.append(normalized)
        return terms[: self.settings.max_results_per_query]

    def _respect_rate_limit(self) -> None:
        elapsed = time.monotonic() - self._last_request_started
        minimum_gap = 0.75
        if elapsed < minimum_gap:
            time.sleep(minimum_gap - elapsed)
        self._last_request_started = time.monotonic()

