from __future__ import annotations

from datetime import datetime, timedelta, timezone


def _to_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


def enrich_match_payload(match: dict, now: datetime | None = None) -> dict:
    current = now or datetime.now(timezone.utc)
    offer = match["offer"]
    valid_until = _to_datetime(offer["valid_until"])
    valid_from = _to_datetime(offer["valid_from"])
    if valid_until and valid_until < current:
        status = "expired"
    elif valid_from and valid_from > current:
        status = "upcoming"
    else:
        status = "active"

    if status == "active" and valid_until and valid_until < current:
        date_state = "expired"
    elif status == "active" and valid_until and valid_until <= current + timedelta(hours=48):
        date_state = "expiring_soon"
    elif status == "upcoming":
        date_state = "upcoming"
    elif status == "expired":
        date_state = "expired"
    else:
        date_state = "active"

    enriched = {
        **match,
        "status": status,
        "date_state": date_state,
        "offer": {
            **offer,
            "valid_from": valid_from.isoformat() if valid_from else None,
            "valid_until": valid_until.isoformat() if valid_until else None,
        },
    }
    return enriched


def filter_matches(
    matches: list[dict],
    *,
    status: str = "all",
    store_slug: str | None = None,
    watched_product_id: str | None = None,
    query: str | None = None,
    max_price: float | None = None,
    provider: str | None = None,
    now: datetime | None = None,
) -> list[dict]:
    enriched = [enrich_match_payload(match, now) for match in matches]
    filtered: list[dict] = []
    query_text = (query or "").casefold().strip()
    for match in enriched:
        offer = match["offer"]
        watch = match["watched_product"]
        if status != "all":
            if status == "expiring":
                if match["date_state"] != "expiring_soon":
                    continue
            elif status == "active":
                if match["status"] != "active":
                    continue
            elif match["status"] != status:
                continue
        if store_slug and offer["store_slug"] != store_slug:
            continue
        if watched_product_id and watch["id"] != watched_product_id:
            continue
        if provider and offer["provider"] != provider:
            continue
        if max_price is not None and offer["price"] is not None and offer["price"] > max_price:
            continue
        if query_text:
            haystack = " ".join(
                [
                    offer["title"] or "",
                    offer["description"] or "",
                    offer["store_name"] or "",
                    offer["store_chain"] or "",
                    offer["provider"] or "",
                    watch["name"] or "",
                ]
            ).casefold()
            if query_text not in haystack:
                continue
        filtered.append(match)
    return filtered


def group_matches(matches: list[dict], by: str) -> list[dict]:
    grouped: dict[str, dict] = {}
    for match in matches:
        if by == "store":
            key = match["offer"]["store_slug"]
            group = grouped.setdefault(
                key,
                {
                    "key": key,
                    "title": match["offer"]["store_chain"] or match["offer"]["store_name"],
                    "subtitle": match["offer"]["store_name"],
                    "matches": [],
                },
            )
        elif by == "product":
            key = match["watched_product"]["id"]
            group = grouped.setdefault(
                key,
                {
                    "key": key,
                    "title": match["watched_product"]["name"],
                    "subtitle": "Competing stores",
                    "matches": [],
                },
            )
        else:
            raise ValueError(f"Unsupported grouping: {by}")
        group["matches"].append(match)

    groups = list(grouped.values())
    for group in groups:
        group["match_count"] = len(group["matches"])
        group["matches"] = sort_matches(group["matches"], by="score")
    return sorted(groups, key=lambda item: (-item["match_count"], item["title"].casefold()))


def sort_matches(matches: list[dict], by: str) -> list[dict]:
    if by == "price":
        return sorted(
            matches,
            key=lambda match: (
                match["offer"]["price"] is None,
                match["offer"]["price"] if match["offer"]["price"] is not None else float("inf"),
                -match["score"],
            ),
        )
    if by == "expires":
        return sorted(
            matches,
            key=lambda match: (
                match["status"] == "expired",
                match["offer"]["valid_until"] is None,
                match["offer"]["valid_until"] or "9999-12-31T23:59:59+00:00",
            ),
        )
    if by == "score":
        return sorted(matches, key=lambda match: (-match["score"], match["offer"]["title"].casefold()))
    raise ValueError(f"Unsupported sort: {by}")


def build_dashboard(matches: list[dict]) -> dict:
    active = filter_matches(matches, status="active")
    upcoming = filter_matches(matches, status="upcoming")
    expiring = filter_matches(matches, status="expiring")
    return {
        "active_count": len(active),
        "upcoming_count": len(upcoming),
        "expiring_count": len(expiring),
        "stores_with_matches": len({match["offer"]["store_slug"] for match in active}),
        "best_matches": sort_matches(active, by="score")[:5],
        "expiring_soon": sort_matches(expiring, by="expires")[:5],
        "upcoming": sort_matches(upcoming, by="expires")[:5],
    }
