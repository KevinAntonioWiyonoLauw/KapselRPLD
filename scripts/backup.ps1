# Backup & restore database middleware (metadata integrasi).
#   powershell -ExecutionPolicy Bypass -File scripts/backup.ps1            # buat backup
#   powershell -ExecutionPolicy Bypass -File scripts/backup.ps1 -Restore backups\middleware_YYYYMMDD_HHMMSS.sql
param(
  [string]$Restore = ""
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$dir = Join-Path $root "backups"
New-Item -ItemType Directory -Force -Path $dir | Out-Null

if ($Restore -ne "") {
  Write-Host "Restoring from $Restore ..." -ForegroundColor Yellow
  Get-Content -Raw $Restore | docker compose exec -T db psql -U middleware -d middleware
  Write-Host "Restore selesai." -ForegroundColor Green
  exit 0
}

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$file = Join-Path $dir "middleware_$stamp.sql"
Write-Host "Backing up to $file ..." -ForegroundColor Cyan
docker compose exec -T db pg_dump -U middleware -d middleware --clean --if-exists | Out-File -Encoding utf8 $file
Write-Host "Backup selesai: $file" -ForegroundColor Green
