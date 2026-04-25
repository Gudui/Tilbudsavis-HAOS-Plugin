param(
    [switch]$Direct
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$Python = "py -3.12"

if ($Direct) {
    Invoke-Expression "$Python -m pip install --user -r addon/requirements.txt"
    $env:PYTHONPATH = "$Root\addon"
    if (-not $env:OFFER_RADAR_DATA_DIR) {
        $env:OFFER_RADAR_DATA_DIR = "$Root\data"
    }
    if (-not $env:OFFER_RADAR_PROVIDER) {
        $env:OFFER_RADAR_PROVIDER = "mock"
    }
    if (-not $env:OFFER_RADAR_PORT) {
        $env:OFFER_RADAR_PORT = "8099"
    }
    Invoke-Expression "$Python -m uvicorn app.main:app --reload --host 0.0.0.0 --port $env:OFFER_RADAR_PORT"
    exit $LASTEXITCODE
}

docker compose up --build
