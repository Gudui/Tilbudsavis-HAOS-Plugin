from __future__ import annotations

import unicodedata


CHAIN_ALIASES = {
    "rema1000": "REMA 1000",
    "rema-1000": "REMA 1000",
    "rema 1000": "REMA 1000",
    "foetex": "føtex",
    "føtex": "føtex",
    "365discount": "365discount",
    "365 discount": "365discount",
}


def _normalize_key(value: str | None) -> str:
    text = (value or "").strip().casefold()
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(character for character in normalized if not unicodedata.combining(character))
    cleaned = []
    for character in ascii_text:
        if character.isalnum():
            cleaned.append(character)
        elif character in {" ", "-", "_", "/"}:
            cleaned.append(" ")
    return " ".join("".join(cleaned).split())


def canonicalize_chain_name(value: str | None) -> str | None:
    if not value:
        return None
    normalized = _normalize_key(value)
    if not normalized:
        return None
    if normalized in CHAIN_ALIASES:
        return CHAIN_ALIASES[normalized]
    return value.strip()


def normalize_store_slug(chain_name: str | None, store_name: str | None = None) -> str:
    candidate = canonicalize_chain_name(chain_name) or store_name or "unknown-store"
    key = _normalize_key(candidate)
    return key.replace(" ", "-") or "unknown-store"


def humanize_store_slug(slug: str) -> str:
    normalized = canonicalize_chain_name(slug)
    if normalized:
        return normalized
    return slug.replace("-", " ").strip().title()
