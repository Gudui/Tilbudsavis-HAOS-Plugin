# Build Plan

## Decision record

- Use case: personal-use only.
- Provider: eTilbudsavis/Tjek via available undocumented/unofficial API behavior.
- Catalogue scope: all stores/chains/categories exposed by the provider for the configured search/location.
- Offer scope: watched-product matches only.
- Runtime: Home Assistant OS add-on.
- Local testability: must run on Debian; should also run on Windows.
- Local harness: Docker Compose first, direct Python second.
- Stack: Python FastAPI, SQLite, vanilla PWA UI.
- Mobile: responsive installable PWA first; optional Capacitor shell later.

## Phase 0 — Guardrails and provider reconnaissance

Goal: prevent provider-specific brittleness from infecting the app.

Tasks:

- Keep `OfferProvider` interface stable.
- Add eTilbudsavis adapter as one implementation only.
- Implement network timeout, retry, user-agent, and rate limit.
- Record sample JSON fixtures from a small number of search terms.
- Write normalization tests against fixtures.
- Add diagnostics page or log view for last sync status.

Acceptance criteria:

- App can run entirely against fixture/mock data.
- Provider adapter can be disabled without breaking UI.
- The undocumented endpoint details are centralized in one file.

## Phase 1 — Local vertical slice

Goal: useful app with no cloud dependencies and no Home Assistant dependency during development.

Tasks:

- Create SQLite tables for watches, offers, matches, sync runs.
- Implement add/list/delete watches.
- Implement manual sync button.
- Query provider once per active watch alias.
- Upsert normalized offers.
- Compute matches after sync.
- Display match cards grouped by store/chain.
- Add date-state tabs: active today, upcoming, expiring soon, all.
- Add Docker Compose dev harness.
- Add Debian and Windows scripts for start/test.
- Add env-var config overrides for local development.

Acceptance criteria:

- `docker compose up --build` starts the app on Debian.
- `./scripts/test.sh` passes on Debian.
- `.\scripts\dev.ps1` starts the app on Windows with Docker Desktop.
- `.\scripts\test.ps1` passes on Windows with Python 3.12+.
- User can add `pepsi max` and run sync.
- Matching offers appear grouped by store.
- Empty states explain whether there are no watches, no sync, or no matches.
- Works in desktop browser and mobile viewport.

## Phase 2 — Home Assistant add-on hardening

Goal: robust HAOS deployment without breaking local testability.

Tasks:

- Ensure DB and logs live under `/data` in the container.
- Read add-on options from `/data/options.json`.
- Preserve env-var overrides for local Compose/direct Python.
- Support Home Assistant Ingress path handling using relative URLs.
- Add health endpoint.
- Add scheduled sync via APScheduler.
- Add backup/export/import JSON.
- Add container logs with structured sync summary.

Acceptance criteria:

- Add-on starts after reboot.
- Manual and scheduled sync work.
- Database survives container restart.
- UI opens through Home Assistant Web UI.
- Same code still passes Debian local tests.

## Phase 3 — UX quality pass

Goal: high-quality daily-use experience.

Tasks:

- Sticky store filter.
- Collapsible store groups.
- “Going to store” mode.
- Offer detail drawer.
- Match reasons.
- Price per liter/kg parser for common Danish quantity formats.
- Fast local filtering without full page reload.
- PWA manifest and service worker.

Acceptance criteria:

- In under 10 seconds, user can select one store and see relevant offers.
- Each offer card shows title, price, store, validity, and why it matched.
- Mobile UI feels native enough for daily use.

## Phase 4 — Home Assistant integration extras

Goal: make the app useful inside automations.

Tasks:

- Expose optional webhook endpoint for Home Assistant notifications.
- Optional MQTT discovery for sensors:
  - total active matches
  - expiring soon count
  - best offer per watch
- Optional persistent notification trigger when new matches appear.

Acceptance criteria:

- HA automation can notify when a watched product appears.
- User can disable HA integration features.

## Phase 5 — Optional native shell

Goal: native mobile packaging without duplicating app logic.

Recommendation:

- Do not build React Native first.
- Wrap the PWA in Capacitor only if App Store / Play Store packaging becomes necessary.
- Keep the Home Assistant add-on as the canonical backend.

Acceptance criteria:

- Same UI and API are reused.
- No duplicate matching/provider logic exists in mobile client.
