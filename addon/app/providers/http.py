from __future__ import annotations

import json
import logging
import time
from typing import Any

import httpx

from app.config import Settings
from app.providers.base import ProviderError


LOGGER = logging.getLogger("offer_radar.providers")


class ProviderHttpClient:
    def __init__(self, provider_name: str, settings: Settings):
        self.provider_name = provider_name
        self.settings = settings
        self._last_request_started = 0.0
        self._client = httpx.Client(
            timeout=httpx.Timeout(float(settings.provider_timeout_seconds)),
            headers={
                "User-Agent": settings.provider_user_agent,
                "Accept-Language": settings.locale,
            },
        )

    def close(self) -> None:
        self._client.close()

    def get_text(self, url: str, *, params: dict[str, Any] | None = None) -> str:
        response = self._request(url, params=params)
        return response.text

    def get_json(self, url: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
        response = self._request(url, params=params)
        try:
            payload = response.json()
        except json.JSONDecodeError as exc:
            raise ProviderError(
                f"{self.provider_name} returned malformed JSON from {url}",
                status="degraded",
                schema_drift_warning="Malformed JSON response from provider.",
            ) from exc
        if not isinstance(payload, dict):
            raise ProviderError(
                f"{self.provider_name} returned an unexpected JSON payload type from {url}",
                status="degraded",
                schema_drift_warning="Unexpected JSON response type from provider.",
            )
        return payload

    def _request(self, url: str, *, params: dict[str, Any] | None = None) -> httpx.Response:
        attempts = max(0, self.settings.provider_max_retries) + 1
        last_error: str | None = None
        for attempt in range(1, attempts + 1):
            self._respect_rate_limit()
            try:
                response = self._client.get(url, params=params)
                if response.status_code == 429 or response.status_code >= 500:
                    raise httpx.HTTPStatusError(
                        f"Transient provider response: {response.status_code}",
                        request=response.request,
                        response=response,
                    )
                if response.status_code >= 400:
                    raise ProviderError(
                        f"{self.provider_name} request failed with HTTP {response.status_code} for {url}",
                        status="failed",
                    )
                return response
            except ProviderError:
                raise
            except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as exc:
                last_error = str(exc)
                LOGGER.warning(
                    "%s request attempt %s/%s failed",
                    self.provider_name,
                    attempt,
                    attempts,
                    extra={"provider": self.provider_name, "url": url, "error": last_error},
                )
                if attempt >= attempts:
                    raise ProviderError(
                        f"{self.provider_name} request failed after retries: {last_error}",
                        status="degraded",
                    ) from exc
                time.sleep(0.5 * (2 ** (attempt - 1)))
        raise ProviderError(f"{self.provider_name} request failed: {last_error or 'unknown error'}")

    def _respect_rate_limit(self) -> None:
        elapsed = time.monotonic() - self._last_request_started
        minimum_gap = float(self.settings.provider_rate_limit_seconds)
        if elapsed < minimum_gap:
            time.sleep(minimum_gap - elapsed)
        self._last_request_started = time.monotonic()
