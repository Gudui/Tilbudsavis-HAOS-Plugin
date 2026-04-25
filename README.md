# Offer Radar

Offer Radar is a personal-use watched-offer app for Danish catalogue providers. It is built for a lightweight Home Assistant OS add-on first, while staying runnable with Docker Compose on Debian and practical to test on Windows with PowerShell.

## What It Does

- Tracks watched products only, not a general all-offers feed
- Normalizes provider data behind an adapter interface
- Stores everything locally in SQLite
- Presents the same matched data through multiple views:
  - Dashboard
  - Store view
  - Product view
  - Best deals
  - Expiring soon
  - Upcoming

## Stack

- Backend: Python, FastAPI, SQLite
- Frontend: mobile-first PWA with minimal vanilla JavaScript
- Tests: pytest with fixture-backed provider coverage
- Runtime target: Home Assistant OS add-on
- Local harness: Docker Compose and direct Python

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

## Provider Limitations

- The `mock` provider is the default local-safe mode and uses bundled fixtures.
- The `etilbudsavis` adapter is intentionally isolated and treated as brittle.
- No live provider access is required for tests.
- The live unofficial adapter only runs if `OFFER_RADAR_ETILBUDSAVIS_SEARCH_URL` is configured.
- Do not depend on undocumented provider fields outside the adapter layer.

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

Build the add-on container directly:

```bash
docker build ./addon
```

## Notes

- On first mock-mode startup, the app seeds a small starter watch list so the fixture sync produces visible matches in the UI baseline.
- Expired offers are excluded from active views.
- Upcoming offers are intentionally separated from active offers.
- Store grouping is first-class, but product comparisons and best-deal sorting use the same normalized match data.

