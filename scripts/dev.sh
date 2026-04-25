#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

if [[ "${1:-}" == "--direct" ]]; then
  python3 -m venv .venv
  # shellcheck disable=SC1091
  source .venv/bin/activate
  python -m pip install --upgrade pip
  python -m pip install -r addon/requirements.txt
  export PYTHONPATH="${ROOT_DIR}/addon"
  export OFFER_RADAR_DATA_DIR="${OFFER_RADAR_DATA_DIR:-${ROOT_DIR}/data}"
  export OFFER_RADAR_PROVIDER="${OFFER_RADAR_PROVIDER:-mock}"
  export OFFER_RADAR_PORT="${OFFER_RADAR_PORT:-8099}"
  exec python -m uvicorn app.main:app --reload --host 0.0.0.0 --port "${OFFER_RADAR_PORT}"
fi

exec docker compose up --build

