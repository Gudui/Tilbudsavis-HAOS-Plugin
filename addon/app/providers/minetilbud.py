from __future__ import annotations

import hashlib
import html
import json
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from app.config import Settings
from app.models import NormalizedOffer, ProviderFetchResult, WatchedProduct
from app.providers.base import ProviderError
from app.providers.http import ProviderHttpClient
from app.services.store_normalization import canonicalize_chain_name, humanize_store_slug, normalize_store_slug


@dataclass(slots=True)
class CatalogReference:
    url: str
    store_slug: str
    store_chain: str
    store_name: str


def _parse_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    cleaned = str(value).replace("kr.", "").replace("kr", "").replace(",", ".")
    digits = "".join(character for character in cleaned if character.isdigit() or character == ".")
    try:
        return float(digits) if digits else None
    except ValueError:
        return None


def _parse_datetime(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    text = str(value).strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _first_non_empty(*values: Any) -> Any:
    return next((value for value in values if value not in (None, "")), None)


def _get_nested(data: dict[str, Any], *keys: str) -> Any:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def discover_catalogs_from_homepage(
    html_text: str,
    *,
    base_url: str,
    store_filters: list[str] | None = None,
) -> list[CatalogReference]:
    soup = BeautifulSoup(html_text, "html.parser")
    filters = {item.casefold() for item in (store_filters or []) if item.strip()}
    catalogs: dict[str, CatalogReference] = {}
    for anchor in soup.find_all("a", href=True):
        href = anchor.get("href", "").strip()
        if not href.startswith("/katalog/"):
            continue
        full_url = urljoin(base_url, href)
        parts = [part for part in urlparse(full_url).path.rstrip("/").split("/") if part]
        if len(parts) < 3 or parts[0] != "katalog":
            continue
        normalized_path = "/" + "/".join(parts) + "/"
        full_url = urljoin(base_url.rstrip("/") + "/", normalized_path.lstrip("/"))
        store_slug = parts[1]
        store_chain = canonicalize_chain_name(store_slug) or humanize_store_slug(store_slug)
        if filters and store_slug.casefold() not in filters and store_chain.casefold() not in filters:
            continue
        catalogs.setdefault(
            full_url,
            CatalogReference(
                url=full_url,
                store_slug=store_slug,
                store_chain=store_chain,
                store_name=store_chain,
            ),
        )
    return list(catalogs.values())


def _balanced_json_candidates(script_text: str) -> list[str]:
    candidates: list[str] = []
    starts = [match.start() for match in re.finditer(r"[\{\[]", script_text[:200000])]
    for start in starts[:12]:
        candidate = _extract_balanced_json(script_text, start)
        if candidate:
            candidates.append(candidate)
    return candidates


def _extract_balanced_json(text: str, start: int) -> str | None:
    opening = text[start]
    closing = "}" if opening == "{" else "]"
    depth = 0
    in_string = False
    escape = False
    for index in range(start, min(len(text), start + 250000)):
        character = text[index]
        if in_string:
            if escape:
                escape = False
            elif character == "\\":
                escape = True
            elif character == '"':
                in_string = False
            continue
        if character == '"':
            in_string = True
        elif character == opening:
            depth += 1
        elif character == closing:
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None


def _decode_json_parse_strings(script_text: str) -> list[Any]:
    objects: list[Any] = []
    for match in re.finditer(r"JSON\.parse\(\s*(['\"])(?P<body>.*?)(?<!\\)\1\s*\)", script_text[:200000], re.DOTALL):
        body = match.group("body")
        decoded = html.unescape(body.encode("utf-8").decode("unicode_escape"))
        try:
            objects.append(json.loads(decoded))
        except json.JSONDecodeError:
            continue
    return objects


def extract_embedded_json_objects(html_text: str) -> list[Any]:
    soup = BeautifulSoup(html_text, "html.parser")
    objects: list[Any] = []
    seen: set[str] = set()
    for script in soup.find_all("script"):
        content = script.string or script.get_text() or ""
        if not content.strip():
            continue
        if script.get("type") == "application/json":
            try:
                payload = json.loads(content)
            except json.JSONDecodeError:
                payload = None
            if payload is not None:
                key = json.dumps(payload, sort_keys=True, default=str)
                if key not in seen:
                    seen.add(key)
                    objects.append(payload)
        for payload in _decode_json_parse_strings(content):
            key = json.dumps(payload, sort_keys=True, default=str)
            if key not in seen:
                seen.add(key)
                objects.append(payload)
        for candidate in _balanced_json_candidates(content):
            try:
                payload = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            key = json.dumps(payload, sort_keys=True, default=str)
            if key not in seen:
                seen.add(key)
                objects.append(payload)
    return objects


def collect_offer_like_objects(payload: Any) -> list[dict[str, Any]]:
    collected: list[dict[str, Any]] = []
    seen: set[str] = set()

    def visit(node: Any) -> None:
        if isinstance(node, dict):
            if _looks_like_offer_object(node):
                key = json.dumps(node, sort_keys=True, default=str)
                if key not in seen:
                    seen.add(key)
                    collected.append(node)
                for child_key, value in node.items():
                    if node.get("kind") == "zone" and child_key == "overrides":
                        continue
                    visit(value)
                return
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            for item in node:
                visit(item)

    visit(payload)
    return collected


def _looks_like_offer_object(node: dict[str, Any]) -> bool:
    keys = {str(key).casefold() for key in node.keys()}
    if node.get("kind") == "zone" and isinstance(node.get("overrides"), dict):
        overrides = {str(key).casefold() for key in node["overrides"].keys()}
        return bool({"title", "name", "text"} & overrides and {"price", "currentprice"} & overrides)
    titleish = {"title", "name", "text", "heading"} & keys
    priceish = {"price", "priceinfo", "currentprice", "overrides"} & keys
    imageish = {"image", "imageurl", "media"} & keys
    return bool(titleish and (priceish or imageish))


def normalize_minetilbud_offer(raw_offer: dict[str, Any], catalog: CatalogReference) -> NormalizedOffer:
    overrides = raw_offer.get("overrides") if isinstance(raw_offer.get("overrides"), dict) else {}
    title = _first_non_empty(
        overrides.get("title"),
        raw_offer.get("title"),
        raw_offer.get("name"),
        raw_offer.get("text"),
        "Untitled offer",
    )
    description = _first_non_empty(
        overrides.get("description"),
        raw_offer.get("description"),
        raw_offer.get("subtitle"),
    )
    price = _parse_float(
        _first_non_empty(
            overrides.get("price"),
            raw_offer.get("price"),
            raw_offer.get("currentPrice"),
            _get_nested(raw_offer, "price", "current"),
        )
    )
    unit_text = _first_non_empty(
        overrides.get("unitText"),
        overrides.get("unit"),
        raw_offer.get("unitText"),
        raw_offer.get("size"),
    )
    image_url = _first_non_empty(
        overrides.get("image"),
        overrides.get("imageUrl"),
        raw_offer.get("image"),
        raw_offer.get("imageUrl"),
        _get_nested(raw_offer, "media", "url"),
        _get_nested(raw_offer, "image", "url"),
    )
    valid_from = _parse_datetime(
        _first_non_empty(raw_offer.get("validFrom"), overrides.get("validFrom"), _get_nested(raw_offer, "catalog", "validFrom"))
    )
    valid_until = _parse_datetime(
        _first_non_empty(raw_offer.get("validUntil"), overrides.get("validUntil"), _get_nested(raw_offer, "catalog", "validUntil"))
    )
    page_number = _first_non_empty(raw_offer.get("page"), raw_offer.get("pageNumber"), overrides.get("page"))
    page_number = int(page_number) if isinstance(page_number, int) or str(page_number).isdigit() else None
    provider_offer_id = _first_non_empty(raw_offer.get("id"), raw_offer.get("offerId"), raw_offer.get("zoneId"))
    if not provider_offer_id:
        provider_offer_id = hashlib.sha1(
            f"{catalog.url}|{title}|{price}|{page_number}".encode("utf-8")
        ).hexdigest()[:16]

    return NormalizedOffer(
        id=f"minetilbud:{provider_offer_id}",
        provider="minetilbud",
        provider_offer_id=str(provider_offer_id),
        title=str(title),
        description=str(description) if description else None,
        price=price,
        currency="DKK",
        unit_text=str(unit_text) if unit_text else None,
        store_name=catalog.store_name,
        store_chain=catalog.store_chain,
        store_slug=normalize_store_slug(catalog.store_chain, catalog.store_name),
        store_id=catalog.store_slug,
        image_url=str(image_url) if image_url else None,
        valid_from=valid_from,
        valid_until=valid_until,
        source_url=catalog.url,
        catalog_url=catalog.url,
        page_number=page_number,
        raw=raw_offer,
    )


class MineTilbudProvider:
    provider_name = "minetilbud"

    def __init__(self, settings: Settings):
        self.settings = settings

    def fetch_offers(self, watched_products: list[WatchedProduct]) -> ProviderFetchResult:
        del watched_products
        started = time.perf_counter()
        client = ProviderHttpClient(self.provider_name, self.settings)
        offers: dict[str, NormalizedOffer] = {}
        warnings: list[str] = []
        errors: list[str] = []
        schema_drift_warning: str | None = None
        catalogs_discovered = 0
        provider_offers_fetched = 0
        try:
            homepage_html = client.get_text(self.settings.minetilbud_base_url)
            catalogs = discover_catalogs_from_homepage(
                homepage_html,
                base_url=self.settings.minetilbud_base_url,
                store_filters=self.settings.minetilbud_store_filters,
            )
            catalogs_discovered = len(catalogs)
            for catalog in catalogs[: self.settings.minetilbud_max_catalogs_per_sync]:
                try:
                    catalog_html = client.get_text(catalog.url)
                except ProviderError as exc:
                    errors.extend(exc.errors)
                    continue
                json_objects = extract_embedded_json_objects(catalog_html)
                if not json_objects:
                    warning = f"No embedded JSON extracted for MineTilbud catalog {catalog.url}"
                    warnings.append(warning)
                    schema_drift_warning = schema_drift_warning or warning
                    continue
                extracted = []
                for payload in json_objects:
                    extracted.extend(collect_offer_like_objects(payload))
                if not extracted:
                    warning = f"No offer-like objects found in MineTilbud catalog {catalog.url}"
                    warnings.append(warning)
                    schema_drift_warning = schema_drift_warning or warning
                    continue
                provider_offers_fetched += len(extracted)
                for raw_offer in extracted:
                    normalized = normalize_minetilbud_offer(raw_offer, catalog)
                    offers[normalized.id] = normalized
        except ProviderError as exc:
            errors.extend(exc.errors)
        finally:
            client.close()

        status = "ok"
        if errors and offers:
            status = "degraded"
        elif errors and not offers:
            status = "failed"
        elif warnings:
            status = "degraded"

        return ProviderFetchResult(
            provider=self.provider_name,
            offers=list(offers.values()),
            status=status,
            catalogs_discovered=catalogs_discovered,
            provider_offers_fetched=provider_offers_fetched,
            raw_payloads_persisted=len(offers),
            error_count=len(errors),
            warnings=warnings,
            errors=errors,
            last_error=errors[-1] if errors else None,
            schema_drift_warning=schema_drift_warning,
            duration_ms=int((time.perf_counter() - started) * 1000),
        )
