from __future__ import annotations

from typing import Protocol

from app.models import NormalizedOffer, WatchedProduct


class ProviderError(Exception):
    pass


class OfferProvider(Protocol):
    provider_name: str

    def fetch_offers(self, watched_products: list[WatchedProduct]) -> list[NormalizedOffer]:
        ...

