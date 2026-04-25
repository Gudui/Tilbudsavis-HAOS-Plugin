from __future__ import annotations

from typing import Protocol

from app.models import ProviderFetchResult, WatchedProduct


class ProviderError(Exception):
    def __init__(
        self,
        message: str,
        *,
        status: str = "failed",
        schema_drift_warning: str | None = None,
        errors: list[str] | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.schema_drift_warning = schema_drift_warning
        self.errors = errors or [message]


class OfferProvider(Protocol):
    provider_name: str

    def fetch_offers(self, watched_products: list[WatchedProduct]) -> ProviderFetchResult:
        ...

