# Local Development

Offer Radar supports three practical runtime paths with the same codebase.

## Docker Compose

Recommended for Debian and the easiest shared baseline for Windows.

```bash
cp .env.example .env
docker compose up --build
```

What this gives you:

- app served on `http://localhost:8099`
- SQLite persisted in `./data/offer_radar.db`
- `/data/options.json` compatibility through the mounted `./data` directory
- provider selection and live-test flags controlled through `./.env`

## Direct Python on Debian

```bash
cp .env.example .env
./scripts/dev.sh --direct
```

The script creates `.venv`, installs [`addon/requirements.txt`](/C:/Users/dhj/repos/Tilbudsavis-HAOS-Plugin/addon/requirements.txt), sets `PYTHONPATH=addon`, and starts Uvicorn with `--reload`.

Run tests with:

```bash
./scripts/test.sh
```

## Direct Python on Windows PowerShell

```powershell
Copy-Item .env.example .env
.\scripts\dev.ps1 -Direct
```

Run tests with:

```powershell
.\scripts\test.ps1
```

## Home Assistant-style local options

You can simulate add-on config locally by creating `./data/options.json`:

```json
{
  "providers": ["mock"],
  "latitude": 55.6761,
  "longitude": 12.5683,
  "radius_meters": 25000,
  "locale": "da_DK",
  "sync_interval_minutes": 0,
  "max_results_per_query": 24,
  "provider_timeout_seconds": 15,
  "provider_rate_limit_seconds": 2,
  "provider_max_retries": 2,
  "etilbudsavis_base_url": "https://api.etilbudsavis.dk",
  "etilbudsavis_search_url": "",
  "etilbudsavis_locale": "da_DK",
  "etilbudsavis_radius_meters": 10000,
  "etilbudsavis_max_results_per_query": 24,
  "minetilbud_base_url": "https://minetilbud.dk",
  "minetilbud_max_catalogs_per_sync": 50,
  "minetilbud_store_filters": []
}
```

Env vars still override values from `options.json`.

## Provider modes

- `mock`: default, deterministic, fully offline
- `etilbudsavis`: unofficial API-style adapter with retries, rate limiting, explicit user agent, schema-drift warnings, and fixture-backed tests
- `minetilbud`: homepage-driven catalog discovery plus embedded-JSON extraction from current catalog pages

## Recommended local settings

- Keep `OFFER_RADAR_PROVIDERS=mock` for normal development and CI-like runs.
- Use `OFFER_RADAR_PROVIDERS=mock,etilbudsavis,minetilbud` only when you want a local mixed-provider sync.
- Leave `OFFER_RADAR_LIVE_PROVIDER_TESTS=false` unless you explicitly want live smoke tests.
- When enabling live providers, keep the conservative defaults for timeout, rate limit, and retries unless you have a clear reason to change them.

## Live smoke tests

Live smoke tests are optional and disabled by default. They are not part of normal CI.

Debian:

```bash
export OFFER_RADAR_LIVE_PROVIDER_TESTS=true
./scripts/test.sh
```

Windows PowerShell:

```powershell
$env:OFFER_RADAR_LIVE_PROVIDER_TESTS='true'
.\scripts\test.ps1
```

When enabled, the smoke tests attempt low-volume real requests against the configured live providers. They are intentionally conservative and may still fail if upstream HTML or API structures change.

## Validation checklist

- Root UI loads at `/`
- `/health` returns `status: ok`
- `POST /api/sync` succeeds with mock fixtures
- `GET /api/providers` returns provider health snapshots
- Active views exclude expired offers
- Upcoming and expiring offers are visible separately
