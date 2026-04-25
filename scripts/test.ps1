$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Python = "py -3.12"
Invoke-Expression "$Python -m pip install --user -r addon/requirements.txt"
$env:PYTHONPATH = "$Root\addon"
$TempRoot = "$Root\.pytest-tmp"
$CacheRoot = "$Root\.pytest-cache"
New-Item -ItemType Directory -Force -Path $TempRoot | Out-Null
New-Item -ItemType Directory -Force -Path $CacheRoot | Out-Null
$env:TMP = $TempRoot
$env:TEMP = $TempRoot
Invoke-Expression "$Python -m compileall addon/app tests"
Invoke-Expression "$Python -m pytest -q --basetemp `"$TempRoot`" -o cache_dir=`"$CacheRoot`""
