#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r addon/requirements.txt
mkdir -p .pytest-tmp .pytest-cache
export TMPDIR="${ROOT_DIR}/.pytest-tmp"
PYTHONPATH="${ROOT_DIR}/addon" python -m compileall addon/app tests
PYTHONPATH="${ROOT_DIR}/addon" python -m pytest -q --basetemp "${ROOT_DIR}/.pytest-tmp" -o cache_dir="${ROOT_DIR}/.pytest-cache"
