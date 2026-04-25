from __future__ import annotations

from collections import Counter

from app.config import Settings
from app.db import Database
from app.models import ProviderFetchResult
from app.providers.base import ProviderError
from app.providers.registry import build_enabled_providers, get_known_provider_names
from app.services.matching import build_matches


def run_sync(database: Database, settings: Settings, selected_provider: str | None = None) -> dict:
    watched_products = database.list_watched_products()
    if not watched_products:
        providers = [selected_provider] if selected_provider else settings.providers
        runs = [
            database.record_sync_run(
                provider=provider,
                status="degraded",
                error_count=1,
                errors=["No watched products configured."],
                error="No watched products configured.",
            )
            for provider in providers
        ]
        return {"status": "degraded", "providers": runs, "matches_created_total": 0, "offers_fetched_total": 0}

    provider_results: list[ProviderFetchResult] = []
    for provider in build_enabled_providers(settings, selected_provider):
        try:
            result = provider.fetch_offers(watched_products)
        except ProviderError as exc:
            result = ProviderFetchResult(
                provider=provider.provider_name,
                status=exc.status,
                error_count=len(exc.errors),
                errors=exc.errors,
                last_error=str(exc),
                schema_drift_warning=exc.schema_drift_warning,
            )
        provider_results.append(result)
        if result.offers:
            database.upsert_offers(result.offers)

    all_offers = database.list_offers()
    matches = build_matches(watched_products, all_offers)
    database.replace_matches(matches)

    matches_by_provider = Counter()
    offers_by_id = {offer.id: offer for offer in all_offers}
    for match in matches:
        offer = offers_by_id.get(match.offer_id)
        if offer:
            matches_by_provider[offer.provider] += 1

    runs = [
        database.record_sync_run(
            provider=result.provider,
            status=result.status,
            catalogs_discovered=result.catalogs_discovered,
            provider_offers_fetched=result.provider_offers_fetched,
            normalized_offers_saved=result.normalized_offers_saved,
            raw_payloads_persisted=result.raw_payloads_persisted,
            matches_created=matches_by_provider.get(result.provider, 0),
            error_count=result.error_count,
            warnings=result.warnings,
            errors=result.errors,
            error=result.last_error,
            schema_drift_warning=result.schema_drift_warning,
            duration_ms=result.duration_ms,
        )
        for result in provider_results
    ]

    statuses = {result.status for result in provider_results}
    overall_status = "ok"
    if "failed" in statuses and len(statuses) == 1:
        overall_status = "failed"
    elif "failed" in statuses or "degraded" in statuses:
        overall_status = "degraded"

    return {
        "status": overall_status,
        "providers": runs,
        "offers_fetched_total": sum(result.provider_offers_fetched for result in provider_results),
        "matches_created_total": len(matches),
    }


def list_provider_health(database: Database, settings: Settings) -> list[dict]:
    return database.list_provider_snapshots(settings.providers, get_known_provider_names())
