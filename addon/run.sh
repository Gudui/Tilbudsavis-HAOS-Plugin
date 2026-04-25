#!/usr/bin/env sh
set -eu

PORT="${PORT:-8099}"
export PORT
export OFFER_RADAR_OPTIONS_PATH="${OFFER_RADAR_OPTIONS_PATH:-/data/options.json}"
export OFFER_RADAR_DATA_DIR="${OFFER_RADAR_DATA_DIR:-/data}"

mkdir -p "${OFFER_RADAR_DATA_DIR}"

if [ -f "${OFFER_RADAR_OPTIONS_PATH}" ]; then
  echo "Offer Radar: loading runtime with options from ${OFFER_RADAR_OPTIONS_PATH}"
else
  echo "Offer Radar: starting without Home Assistant options file"
fi

exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT}"

