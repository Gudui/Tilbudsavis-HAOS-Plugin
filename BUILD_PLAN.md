# Build Plan

## Current baseline target

Create a reliable watched-offer baseline that:

- runs as a Home Assistant add-on
- runs locally with Docker Compose
- is testable directly with Python on Debian and Windows
- keeps provider-specific logic isolated
- supports dashboard, store, product, best-deals, expiring, and upcoming views from the same normalized match data

## Phase 1: Runtime and persistence

- Add add-on packaging files under `addon/`
- Load config from env vars and `/data/options.json`
- Initialize SQLite automatically under the configured data directory
- Document Docker Compose, direct Python, and add-on runtime modes

## Phase 2: Domain baseline

- Define canonical watched-product and normalized-offer models
- Add SQLite repositories for watches, offers, matches, and sync runs
- Keep provider adapters behind the `OfferProvider` interface
- Persist normalized offers plus raw payloads for diagnostics

## Phase 3: Matching and query views

- Match watched products with include/exclude keywords
- Respect optional max price and store filters
- Distinguish active, expired, upcoming, and expiring-soon states
- Expose grouped-by-store and grouped-by-product queries
- Expose sorted-by-price and sorted-by-expiry queries

## Phase 4: First usable UX

- Render a mobile-first PWA shell
- Show dashboard, store, product, best-deals, expiring, and upcoming views
- Allow focused inspection of a single store
- Allow direct comparison of one watched product across stores
- Keep frontend logic thin by consuming backend query endpoints

## Phase 5: Fixtures, tests, and CI

- Use fixture-backed provider mapping tests
- Keep unit tests fully offline
- Add health, config, DB, matching, grouping, sorting, and API smoke coverage
- Run tests in GitHub Actions on push and pull request

