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
    title: str
    description: str | None
    price: float | None
    currency: str | None
    store_name: str
    store_chain: str | None
    store_slug: str
    image_url: str | None
    valid_from: datetime | None
    valid_until: datetime | None
    source_url: str | None
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

