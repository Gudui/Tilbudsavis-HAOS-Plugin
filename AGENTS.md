# Agent Instructions

You are building Offer Radar as a personal-use Home Assistant OS add-on.

## Primary objective

Build a lightweight local app that fetches offers from eTilbudsavis/Tjek-style sources, matches only watched products, and presents a high-quality mobile-first UI grouped by store and validity window.

## Hard constraints

- Target runtime: Home Assistant OS add-on.
- Single container.
- SQLite under `/data/offer_radar.db`.
- No external hosted database.
- No public SaaS assumptions.
- No user-account/auth system in MVP; Home Assistant add-on access is enough.
- Mobile support is via responsive PWA and Home Assistant app Web UI first.
- Provider integrations must stay behind adapter interfaces.
- eTilbudsavis integration is unofficial/undocumented and must be treated as brittle.
- Do not bypass authentication, paywalls, bot protections, CAPTCHAs, or technical access controls.
- Implement polite rate limiting and caching.
- Keep source attribution in offer detail data.
- Store raw provider payloads for diagnostics only.
- Domain logic must be testable without network access.

## Product constraints

- Only show watched-product matches.
- Do not build a general all-offers feed.
- Store grouping is first-class.
- The catalogue/store universe should follow whatever eTilbudsavis exposes; do not manually curate a fixed chain list.
- Offers shift on different days, so validity windows must be precise and visible.
- Active today, upcoming, and expiring soon must be separate date states.

## Implementation order

1. SQLite schema and repository helpers.
2. Watch management API.
3. Mock provider fixtures.
4. Matching/ranking engine.
5. Store-grouped UI.
6. eTilbudsavis adapter behind `OfferProvider`.
7. Background sync every configured interval.
8. PWA polish, offline shell, loading/empty/error states.
9. Optional Home Assistant sensors/events.
10. Optional Capacitor shell only after the PWA is stable.

## Definition of done for MVP

- Add/edit/delete watched products.
- Sync offers for watches and aliases.
- Normalize offer fields into canonical structure.
- Deduplicate external offers.
- Match and rank offers.
- Display matching offers grouped by store/chain.
- Filter by store, watch, date state, max price, and query.
- Show validity windows clearly.
- App works through Home Assistant Ingress.
- App works on mobile viewport.
- Provider failure degrades gracefully.
- Unit tests cover matching and provider normalization with fixtures.


## Local testability rule

Do not introduce a dependency on Home Assistant OS for normal development. Every backend and UI change must remain runnable through:

- `docker compose up --build` on Debian
- `./scripts/test.sh` on Debian
- `.\scripts\dev.ps1` on Windows PowerShell where Docker Desktop is available
- `.\scripts\test.ps1` on Windows PowerShell where Python 3.12+ is available

The Home Assistant add-on packaging is the deployment target; Docker Compose is the local test harness.
