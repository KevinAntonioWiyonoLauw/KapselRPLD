# Aktifkan REST/FHIR API pada OpenEMR (idempotent).
# Prasyarat: container OpenEMR & DB-nya sudah jalan (profil ehr).
#   docker compose -f docker-compose.yml -f docker-compose.ehr.yml --profile ehr up -d openemr-db openemr
# Jalankan: powershell -ExecutionPolicy Bypass -File scripts/openemr-enable-api.ps1
param(
  [string]$DbContainer = "kapselrpld-openemr-db-1",
  [string]$DbUser = "root",
  [string]$DbPass = "root",
  [string]$DbName = "openemr"
)

$ErrorActionPreference = "Stop"
Write-Host "== Aktifkan globals REST/FHIR API pada $DbContainer ==" -ForegroundColor Cyan
$sql = "UPDATE globals SET gl_value='1' WHERE gl_name IN ('rest_api','rest_fhir_api','rest_system_scopes_api','rest_portal_api'); " +
       "UPDATE globals SET gl_value='1' WHERE gl_name='oauth_password_grant'; " +
       "SELECT gl_name, gl_value FROM globals WHERE gl_name IN ('rest_api','rest_fhir_api','rest_system_scopes_api','oauth_password_grant');"
docker exec $DbContainer mysql "-u$DbUser" "-p$DbPass" $DbName -e $sql
Write-Host "Selesai. Jika perlu, restart container OpenEMR agar global termuat ulang." -ForegroundColor Green
