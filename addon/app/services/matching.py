from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.models import MatchRecord, NormalizedOffer, WatchedProduct
from app.services.store_normalization import canonicalize_chain_name


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def determine_offer_status(offer: NormalizedOffer, now: datetime | None = None) -> str:
    current = now or utc_now()
    if offer.valid_until and offer.valid_until < current:
        return "expired"
    if offer.valid_from and offer.valid_from > current:
        return "upcoming"
    return "active"


def is_expiring_soon(offer: NormalizedOffer, now: datetime | None = None, threshold_hours: int = 48) -> bool:
    current = now or utc_now()
    return (
        determine_offer_status(offer, current) == "active"
        and offer.valid_until is not None
        and offer.valid_until <= current + timedelta(hours=threshold_hours)
    )


def match_offer_to_watch(
    offer: NormalizedOffer,
    watch: WatchedProduct,
    now: datetime | None = None,
) -> MatchRecord | None:
    if not watch.enabled:
        return None

    haystack = " ".join(
        part for part in [offer.title, offer.description or "", offer.store_name, offer.store_chain or ""] if part
    ).casefold()
    include_terms = _unique_terms([watch.name, *watch.keywords])
    matched_keywords = [term for term in include_terms if term.casefold() in haystack]
    if not matched_keywords:
        return None

    excluded = [term for term in _unique_terms(watch.exclude_keywords) if term.casefold() in haystack]
    if excluded:
        return None

    if watch.max_price is not None and offer.price is not None and offer.price > watch.max_price:
        return None

    if watch.store_filters and not _store_filter_matches(offer, watch.store_filters):
        return None

    status = determine_offer_status(offer, now)
    reasons = [f"Matched keywords: {', '.join(matched_keywords)}."]
    if watch.max_price is not None:
        if offer.price is None:
            reasons.append("Watch has a max price, but this offer has no price yet.")
        else:
            reasons.append(f"Price {offer.price:.2f} is within the {watch.max_price:.2f} limit.")
    if watch.store_filters:
        reasons.append("Offer passed the store filter.")
    reasons.append(f"Offer is currently {status}.")

    score = float(len(matched_keywords) * 10)
    score += {"active": 30.0, "upcoming": 15.0, "expired": 0.0}[status]
    if offer.price is not None:
        score += max(0.0, 25.0 - offer.price)
    if is_expiring_soon(offer, now):
        reasons.append("Offer expires soon.")
        score += 5.0

    return MatchRecord(
        id=f"{watch.id}:{offer.id}",
        watched_product_id=watch.id,
        offer_id=offer.id,
        status=status,
        score=score,
        reasons=reasons,
        matched_keywords=matched_keywords,
    )


def build_matches(
    watched_products: list[WatchedProduct],
    offers: list[NormalizedOffer],
    now: datetime | None = None,
) -> list[MatchRecord]:
    matches: list[MatchRecord] = []
    for watch in watched_products:
        for offer in offers:
            match = match_offer_to_watch(offer, watch, now)
            if match:
                matches.append(match)
    return matches


def _store_filter_matches(offer: NormalizedOffer, filters: list[str]) -> bool:
    store_text = f"{offer.store_name} {canonicalize_chain_name(offer.store_chain) or ''}".casefold()
    return any((canonicalize_chain_name(term) or term).casefold() in store_text for term in filters if term.strip())


def _unique_terms(terms: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for term in terms:
        normalized = term.strip()
        key = normalized.casefold()
        if normalized and key not in seen:
            seen.add(key)
            unique.append(normalized)
    return unique
