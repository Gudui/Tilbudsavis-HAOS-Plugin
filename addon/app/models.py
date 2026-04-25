from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class WatchedProduct:
    id: str
    name: str
    keywords: list[str] = field(default_factory=list)
    exclude_keywords: list[str] = field(default_factory=list)
    max_price: float | None = None
    store_filters: list[str] = field(default_factory=list)
    enabled: bool = True


@dataclass(slots=True)
class NormalizedOffer:
    id: str
    provider: str
    provider_offer_id: str | None
    title: str
    description: str | None
    price: float | None
    currency: str | None
    unit_text: str | None
    store_name: str
    store_chain: str | None
    store_slug: str
    store_id: str | None
    image_url: str | None
    valid_from: datetime | None
    valid_until: datetime | None
    source_url: str | None
    catalog_url: str | None
    page_number: int | None
    raw: dict[str, Any]


@dataclass(slots=True)
class MatchRecord:
    id: str
    watched_product_id: str
    offer_id: str
    status: str
    score: float
    reasons: list[str] = field(default_factory=list)
    matched_keywords: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ProviderFetchResult:
    provider: str
    offers: list[NormalizedOffer] = field(default_factory=list)
    status: str = "ok"
    catalogs_discovered: int = 0
    provider_offers_fetched: int = 0
    raw_payloads_persisted: int = 0
    error_count: int = 0
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    last_error: str | None = None
    schema_drift_warning: str | None = None
    duration_ms: int = 0

    @property
    def normalized_offers_saved(self) -> int:
        return len(self.offers)

