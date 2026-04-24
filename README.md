# Offer Radar — Home Assistant OS Add-on Scaffold

Personal-use offer watcher for Danish offers from eTilbudsavis/Tjek-style sources.

This scaffold is optimized for Home Assistant OS while remaining testable on normal development machines:

- Home Assistant OS add-on as production target
- Debian local testing with Docker Compose or direct Python
- Windows local testing with Docker Desktop/PowerShell or direct Python
- Single Docker container
- FastAPI backend
- SQLite database stored under `/data` in containers and `./data` during direct local runs
- Vanilla mobile-first PWA UI
- Background sync every few hours in production
- Provider adapter for the unofficial/undocumented eTilbudsavis search endpoint
- Watched-product matches only; no noisy general feed
- Store-grouped display for “I am going to one place” use cases

## Product position

Offer Radar is not a public SaaS. It is a private household assistant that runs locally and helps you track watched products across whichever stores and catalogues the configured provider exposes.

## Why this stack

Home Assistant OS is add-on/container oriented. A Next.js + Postgres stack is unnecessarily heavy for personal use. This scaffold uses FastAPI + SQLite + vanilla JS because it is small, easy to back up, easy to debug, and works behind Home Assistant Ingress.

## MVP behavior

1. Configure home latitude, longitude, radius, locale, and sync interval.
2. Add watched products such as `pepsi max`, `kaffe`, `hakket oksekød`, `bleer`.
3. Sync queries eTilbudsavis once per watched product and alias.
4. Offers are normalized, deduplicated, matched, ranked, and stored locally.
5. UI shows only matching offers, grouped by store/chain.
6. Mobile users can install the PWA from the browser or use it through the Home Assistant app.

## Important provider note

The included eTilbudsavis provider is intentionally isolated behind an adapter. The endpoint is unofficial and undocumented, so it may change, disappear, rate-limit, or require different parameters. Do not let provider assumptions leak into the domain model or UI.

## Repository layout

```text
addon/                         Home Assistant add-on files
  config.yaml                  Add-on metadata and options schema
  Dockerfile                   Lightweight container image
  run.sh                       Container entrypoint
  requirements.txt             Python runtime dependencies
  app/                         FastAPI application
    main.py                    API and HTML routes
    db.py                      SQLite schema and helpers
    config.py                  Add-on options/env loader
    providers/                 Provider adapter layer
    services/                  Matching and sync logic
    static/                    PWA assets
    templates/                 HTML shell

compose.yaml                   Local Docker Compose harness
.env.example                   Local config defaults
scripts/                       Debian and Windows dev/test scripts
data.example/                  Example options.json
docs/                          Product, architecture, local dev, and build plan
prompts/                       Agent prompts for accelerated implementation
AGENTS.md                      Coding-agent instructions
BUILD_PLAN.md                  Phase plan for the agent
```

## Fast local start — Debian

```bash
cp .env.example .env
./scripts/dev.sh
```

Open `http://localhost:8099`.

## Fast local start — Windows PowerShell

```powershell
Copy-Item .env.example .env
.\scripts\dev.ps1
```

Open `http://localhost:8099`.

## Direct Python development

```bash
cd addon
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
OFFER_RADAR_DATA_DIR=../data OFFER_RADAR_PROVIDER=mock uvicorn app.main:app --reload --host 0.0.0.0 --port 8099
```

## Test commands

Debian:

```bash
./scripts/test.sh
```

Windows PowerShell:

```powershell
.\scripts\test.ps1
```

## Home Assistant OS install path

For a local add-on:

1. Copy `addon/` into an add-on repository folder accessible to Home Assistant.
2. In Home Assistant, enable Advanced Mode.
3. Go to **Settings → Add-ons → Add-on Store → Repositories**.
4. Add the local repository or a Git repo containing this `addon/` folder.
5. Install **Offer Radar**.
6. Configure options.
7. Start the add-on.
8. Open the Web UI.

## First agent task

Read `AGENTS.md`, then implement and test the vertical slice in `BUILD_PLAN.md` Phase 1.
