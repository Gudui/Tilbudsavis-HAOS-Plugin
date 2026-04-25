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
  "provider": "mock",
  "latitude": 55.6761,
  "longitude": 12.5683,
  "radius_meters": 25000,
  "locale": "da_DK",
  "sync_interval_minutes": 0,
  "max_results_per_query": 24,
  "request_timeout_seconds": 12
}
```

Env vars still override values from `options.json`.

## Provider modes

- `mock`: default, deterministic, fully offline
- `etilbudsavis`: unofficial adapter, only safe to use when an explicit search URL is configured

## Validation checklist

- Root UI loads at `/`
- `/health` returns `status: ok`
- `POST /api/sync` succeeds with mock fixtures
- Active views exclude expired offers
- Upcoming and expiring offers are visible separately

