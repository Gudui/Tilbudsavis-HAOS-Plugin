# Offer Radar

Offer Radar is a personal-use watched-offer app for Danish catalogue providers. It is built for a lightweight Home Assistant OS add-on first, while staying runnable with Docker Compose on Debian and practical to test on Windows with PowerShell.

## What It Does

- Tracks watched products only, not a general all-offers feed
- Normalizes provider data behind an adapter interface
- Stores everything locally in SQLite
- Presents the same matched data through multiple views:
  - dashboard
  - store view
  - product view
  - best deals
  - expiring soon
  - upcoming
- Runs multiple providers in one sync without leaking provider-specific fields into matching or UI code
- Surfaces lightweight provider diagnostics in the dashboard and API

## Stack

- Backend: Python, FastAPI, SQLite
- Frontend: mobile-first PWA with minimal vanilla JavaScript
- Tests: pytest with fixture-backed provider coverage
- Runtime target: Home Assistant OS add-on
- Local harness: Docker Compose and direct Python

## Provider Architecture

Provider ingestion stays behind the `OfferProvider` interface in [`addon/app/providers/`](/C:/Users/dhj/repos/Tilbudsavis-HAOS-Plugin/addon/app/providers). The app flow is:

1. Fetch provider data.
2. Normalize each provider payload into the canonical `Offer` model.
3. Persist normalized offers and raw payloads locally in SQLite.
4. Match offers against watched products.
5. Present those matches through dashboard, store, product, best-deals, expiring, and upcoming views.

Current providers:

- `mock`: fully offline fixture-backed provider for normal local development and CI
- `etilbudsavis`: hardened unofficial API adapter with retries, rate limiting, schema-drift diagnostics, and fixture-backed tests
- `minetilbud`: homepage-discovered catalog provider that parses current catalog links from HTML and extracts embedded catalog JSON without JavaScript execution

Provider-specific fields stay inside the adapters. Matching, grouping, sorting, and UI code only consume normalized offers.

## Runtime Modes

### 1. Docker Compose local dev

```bash
cp .env.example .env
docker compose up --build
```

Open [http://localhost:8099](http://localhost:8099).

Persistent local data:

- SQLite: `./data/offer_radar.db`
- Optional Home Assistant-style options file for local testing: `./data/options.json`
- Docker Compose env file: `./.env`

### 2. Direct Python local dev on Debian

```bash
cp .env.example .env
./scripts/dev.sh --direct
```

Manual tests:

```bash
./scripts/test.sh
```

### 3. Direct Python local dev on Windows PowerShell

```powershell
Copy-Item .env.example .env
.\scripts\dev.ps1 -Direct
```

Manual tests:

```powershell
.\scripts\test.ps1
```

### 4. Home Assistant add-on deployment

The add-on files live under [`addon/`](/C:/Users/dhj/repos/Tilbudsavis-HAOS-Plugin/addon).

Basic install flow:

1. Place this repository in a Home Assistant add-on repository.
2. Ensure [`repository.yaml`](/C:/Users/dhj/repos/Tilbudsavis-HAOS-Plugin/repository.yaml) is visible to Home Assistant.
3. Install the `Offer Radar` add-on.
4. Configure options in the add-on UI.
5. Start the add-on and open it through Home Assistant Ingress.

Container persistence path:

- SQLite and runtime data: `/data/offer_radar.db`
- Add-on options file: `/data/options.json`

The entrypoint [`addon/run.sh`](/C:/Users/dhj/repos/Tilbudsavis-HAOS-Plugin/addon/run.sh) supports both add-on mode and non-Home-Assistant env-var mode.

## Configuration

The same settings work from Home Assistant `/data/options.json`, Docker Compose `.env`, or direct Python environment variables.

Important variables:

- `OFFER_RADAR_PROVIDERS=mock,etilbudsavis,minetilbud`
- `OFFER_RADAR_PROVIDER_TIMEOUT_SECONDS=15`
- `OFFER_RADAR_PROVIDER_RATE_LIMIT_SECONDS=2`
- `OFFER_RADAR_PROVIDER_MAX_RETRIES=2`
- `OFFER_RADAR_PROVIDER_USER_AGENT=...`
- `OFFER_RADAR_LIVE_PROVIDER_TESTS=false`
- `ETILBUDSAVIS_BASE_URL=https://api.etilbudsavis.dk`
- `ETILBUDSAVIS_SEARCH_URL=`
- `ETILBUDSAVIS_LOCALE=da_DK`
- `ETILBUDSAVIS_RADIUS_METERS=10000`
- `ETILBUDSAVIS_MAX_RESULTS_PER_QUERY=24`
- `MINETILBUD_BASE_URL=https://minetilbud.dk`
- `MINETILBUD_MAX_CATALOGS_PER_SYNC=50`
- `MINETILBUD_STORE_FILTERS=`

The legacy `OFFER_RADAR_PROVIDER` setting is still read as a fallback for older configs, but new setups should use `OFFER_RADAR_PROVIDERS`.

## Provider Limitations And Caveats

- The `mock` provider is the default local-safe mode and uses bundled fixtures.
- The `etilbudsavis` adapter is intentionally isolated and treated as brittle because it depends on undocumented structures that may change.
- The `minetilbud` adapter discovers current catalogs from the homepage instead of guessing weekly catalog slugs, then extracts embedded JSON from catalog HTML.
- Both live providers can degrade gracefully when HTML or JSON structures drift, results are empty, fields are missing, or requests fail.
- No live provider access is required for unit tests or CI.
- Optional live smoke tests are disabled by default.
- Do not depend on undocumented provider fields outside the adapter layer.

## Provider Health And Diagnostics

Each provider records lightweight sync diagnostics:

- status: `ok`, `degraded`, `failed`, or `disabled`
- last successful sync time
- last error
- last schema-drift warning
- counts for discovered catalogs, fetched offers, normalized offers, matches, and persisted raw payloads

Relevant endpoints:

- `GET /api/providers`
- `GET /api/providers/{provider}/health`
- `GET /api/sync-runs`
- `POST /api/sync`
- `POST /api/sync?provider=etilbudsavis`
- `POST /api/sync?provider=minetilbud`

## Repository Layout

```text
addon/
  app/
    config.py
    db.py
    main.py
    models.py
    providers/
    services/
    static/
    templates/
  config.yaml
  Dockerfile
  requirements.txt
  run.sh

docs/
  local-development.md

scripts/
  dev.sh
  test.sh
  dev.ps1
  test.ps1

tests/
  ...
```

## Useful Commands

Run the app with Docker Compose:

```bash
docker compose up --build
```

Run Debian tests:

```bash
./scripts/test.sh
```

Run Windows tests:

```powershell
.\scripts\test.ps1
```

Run optional live smoke tests:

```bash
OFFER_RADAR_LIVE_PROVIDER_TESTS=true ./scripts/test.sh
```

```powershell
$env:OFFER_RADAR_LIVE_PROVIDER_TESTS='true'
.\scripts\test.ps1
```

Build the add-on container directly:

```bash
docker build ./addon
```

## Testing And CI

- Unit tests are fully offline and do not call live provider endpoints.
- Provider coverage uses bundled fixture payloads for both eTilbudsavis and MineTilbud.
- GitHub Actions runs syntax checks and pytest without requiring live provider access.
- Live smoke tests are opt-in only and are not part of normal CI.

## Troubleshooting

- If a provider reports `degraded`, check `/api/providers` or the dashboard provider cards for `last_error` and `last_schema_drift_warning` details.
- If eTilbudsavis returns no results, confirm locale, location, radius, and max-result settings, and remember the upstream API is undocumented and may drift.
- If MineTilbud stops extracting offers, first check whether homepage discovery still returns `/katalog/` links and whether current catalog pages still embed parseable JSON.
- If you want deterministic testing, keep `OFFER_RADAR_PROVIDERS=mock` and leave live smoke tests disabled.

## Notes

- On first mock-mode startup, the app seeds a small starter watch list so the fixture sync produces visible matches in the UI baseline.
- Expired offers are excluded from active views.
- Upcoming offers are intentionally separated from active offers.
- Store grouping is first-class, but product comparisons and best-deal sorting use the same normalized match data.
