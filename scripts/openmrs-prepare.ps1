# Siapkan OpenMRS reference app agar FHIR2 create (Patient/Encounter/Observation) berhasil.
#
# Latar belakang (temuan nyata terhadap image openmrs/openmrs-reference-application-distro):
#  - FHIR2 mengirim INSERT dengan uuid = NULL eksplisit untuk tabel anak
#    (person_name, patient_identifier, encounter, obs, dst). Karena eksplisit NULL,
#    DEFAULT kolom tidak terpakai -> "Column 'uuid' cannot be null". Solusi: trigger
#    BEFORE INSERT yang mengisi uuid bila NULL.
#  - FHIR2 memetakan identifier.system -> patient_identifier_type lewat tabel
#    fhir_patient_identifier_system (kosong pada reference app) -> tanpa itu
#    "Select a preferred identifier".
#  - FHIR2 memetakan Observation.code (LOINC) -> concept lewat fhir_concept_source
#    (kosong) -> tanpa itu "concept: Cannot be empty or null".
#
# Idempotent: aman dijalankan berulang. Prasyarat: container OpenMRS + DB jalan.
#   docker compose -f docker-compose.yml -f docker-compose.ehr.yml --profile ehr up -d openmrs-db openmrs
# Jalankan:
#   powershell -ExecutionPolicy Bypass -File scripts/openmrs-prepare.ps1
# Setelah menambah mapping identifier/concept, restart OpenMRS agar cache termuat:
#   docker compose -f docker-compose.yml -f docker-compose.ehr.yml --profile ehr restart openmrs
param(
  [string]$DbContainer = "kapselrpld-openmrs-db-1",
  [string]$DbName = "openmrs",
  [string]$RootPass = "openmrs",
  [string]$SystemUrl = "http://openmrs.org/mrn",
  [int]$IdentifierTypeId = 2,   # 2 = "Old Identification Number" (tanpa validator/check digit)
  [int]$LoincConceptSourceId = 6
)

$ErrorActionPreference = "Stop"

function Invoke-Sql([string]$sql) {
  $tmp = [System.IO.Path]::GetTempFileName()
  try {
    [System.IO.File]::WriteAllText($tmp, $sql, (New-Object System.Text.UTF8Encoding($false)))
    Get-Content -Raw $tmp | docker exec -i $DbContainer mysql "-uroot" "-p$RootPass" $DbName
  } finally {
    Remove-Item $tmp -ErrorAction SilentlyContinue
  }
}

Write-Host "== 1) Trigger BEFORE INSERT: isi uuid bila NULL (semua tabel ber-kolom uuid) ==" -ForegroundColor Cyan
$tables = (docker exec $DbContainer mysql "-uroot" "-p$RootPass" $DbName -N -e `
  "SELECT table_name FROM information_schema.columns WHERE table_schema='$DbName' AND column_name='uuid';") 2>$null
$sb = New-Object System.Text.StringBuilder
foreach ($t in ($tables -split "`n" | ForEach-Object { $_.Trim() } | Where-Object { $_ })) {
  [void]$sb.AppendLine("DROP TRIGGER IF EXISTS trg_uuid_$t;")
  [void]$sb.AppendLine("CREATE TRIGGER trg_uuid_$t BEFORE INSERT ON ``$t`` FOR EACH ROW SET NEW.uuid = IFNULL(NEW.uuid, UUID());")
}
Invoke-Sql $sb.ToString()
Write-Host ("   trigger diproses untuk {0} tabel." -f (($tables -split "`n" | Where-Object { $_.Trim() }).Count))

Write-Host "== 2) Daftarkan identifier system '$SystemUrl' -> patient_identifier_type $IdentifierTypeId ==" -ForegroundColor Cyan
Invoke-Sql ("INSERT INTO fhir_patient_identifier_system (patient_identifier_type_id, url, name, creator, date_created, uuid) " +
  "SELECT $IdentifierTypeId, '$SystemUrl', 'OpenMRS MRN', 1, NOW(), UUID() " +
  "WHERE NOT EXISTS (SELECT 1 FROM fhir_patient_identifier_system WHERE patient_identifier_type_id=$IdentifierTypeId AND url='$SystemUrl');")

Write-Host "== 3) Daftarkan LOINC concept source (id $LoincConceptSourceId) ke fhir_concept_source ==" -ForegroundColor Cyan
Invoke-Sql ("INSERT INTO fhir_concept_source (concept_source_id, url, name, creator, date_created, uuid) " +
  "SELECT $LoincConceptSourceId, 'http://loinc.org', 'LOINC', 1, NOW(), UUID() " +
  "WHERE NOT EXISTS (SELECT 1 FROM fhir_concept_source WHERE url='http://loinc.org');")

Write-Host "== 4) Jadikan 'Old Identification Number' default identifier type ==" -ForegroundColor Cyan
Invoke-Sql ("UPDATE global_property SET property_value='8d79403a-c2cc-11de-8d13-0010c6dffd0f' " +
  "WHERE property='emr.defaultPatientIdentifierType';")

Write-Host "== Verifikasi ==" -ForegroundColor Cyan
Invoke-Sql ("SELECT 'identifier_system' AS what, patient_identifier_type_id AS k, url AS v FROM fhir_patient_identifier_system " +
  "UNION ALL SELECT 'concept_source', concept_source_id, url FROM fhir_concept_source;")

Write-Host "Selesai. Restart OpenMRS agar mapping identifier/concept dimuat ke cache:" -ForegroundColor Green
Write-Host "  docker compose -f docker-compose.yml -f docker-compose.ehr.yml --profile ehr restart openmrs"
