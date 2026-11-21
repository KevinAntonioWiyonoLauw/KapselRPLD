# Jalankan semua test (unit + integration + e2e). Prasyarat: stack `docker compose up -d`.
#   powershell -ExecutionPolicy Bypass -File scripts/test-all.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$img = "kapselrpld-backend:latest"
$net = "kapselrpld_default"

Write-Host "== UNIT ==" -ForegroundColor Cyan
docker run --rm -v "${root}\backend:/app" -w /app $img `
  sh -c "pip install -q pytest pytest-asyncio && python -m pytest tests/unit -q"

Write-Host "== INTEGRATION ==" -ForegroundColor Cyan
docker run --rm --network $net --env-file "$root\.env" -v "${root}\backend:/app" -w /app $img `
  sh -c "pip install -q pytest pytest-asyncio && python -m pytest tests/integration -q"

Write-Host "== E2E ==" -ForegroundColor Cyan
docker run --rm --network $net --env-file "$root\.env" -v "${root}\backend:/app" -w /app $img `
  sh -c "pip install -q pytest pytest-asyncio && python -m pytest tests/e2e -q"

Write-Host "ALL TESTS DONE" -ForegroundColor Green
