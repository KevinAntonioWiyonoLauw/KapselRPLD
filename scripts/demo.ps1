# Demo end-to-end middleware FHIR (jalankan dari root repo)
#   powershell -ExecutionPolicy Bypass -File scripts/demo.ps1
$ErrorActionPreference = "Stop"
$base = "http://localhost:8000"
$token = "change_me_admin_token"
$h = @{ Authorization = "Bearer $token"; "Content-Type" = "application/json" }

function Enqueue($src, $tgt, $res) {
  $body = @{ source_system = $src; target_system = $tgt; resource = $res } | ConvertTo-Json -Depth 12
  Invoke-RestMethod -Method Post -Headers $h -Uri "$base/api/v1/jobs/enqueue" -Body $body
}

Write-Host "== Reset metadata ==" -ForegroundColor Cyan
docker compose exec -T db psql -U middleware -d middleware `
  -c "TRUNCATE sync_jobs, job_attempts, conflicts, audit_log RESTART IDENTITY CASCADE;" | Out-Null

$patient = @{ resourceType="Patient"; identifier=@(@{system="http://openmrs.org/mrn"; value="MRN-001"});
              name=@(@{text="Budi Santoso"}) }
$encounter = @{ resourceType="Encounter"; status="finished";
                "class"=@{system="http://terminology.hl7.org/CodeSystem/v3-ActCode"; code="AMB"};
                subject=@{reference="Patient/MRN-001"}; period=@{start="2026-01-10T09:00:00+00:00"};
                serviceProvider=@{reference="Organization/1000001"};
                statusHistory=@(@{status="finished"; period=@{start="2026-01-10T09:00:00+00:00"; end="2026-01-10T09:30:00+00:00"}});
                diagnosis=@(@{condition=@{reference="Condition/example"};
                              use=@{coding=@(@{system="http://terminology.hl7.org/CodeSystem/diagnosis-role"; code="billing"})}}) }
$obs = @{ resourceType="Observation"; status="final"; code=@{text="body_temp"};
          subject=@{reference="Patient/MRN-001"}; effectiveDateTime="2026-01-10T09:15:00+00:00";
          issued="2026-01-10T09:15:00+00:00";
          valueQuantity=@{value=36.8; unit="Cel"} }

Write-Host "== Enqueue 5 job ==" -ForegroundColor Cyan
Enqueue "openmrs" "openemr"   $patient   | Out-Null
Enqueue "openmrs" "satusehat" $patient   | Out-Null
Enqueue "openmrs" "openemr"   $encounter | Out-Null
Enqueue "openmrs" "satusehat" $encounter | Out-Null
Enqueue "openmrs" "satusehat" $obs       | Out-Null

Write-Host "== Menunggu worker ==" -ForegroundColor Cyan
Start-Sleep -Seconds 8

Write-Host "== Status job ==" -ForegroundColor Green
docker compose exec -T db psql -U middleware -d middleware `
  -c "SELECT resource_type, status, attempt_count FROM sync_jobs ORDER BY created_at;"

Write-Host "== Metrik ==" -ForegroundColor Green
Invoke-RestMethod -Headers $h "$base/api/v1/metrics" | ConvertTo-Json -Depth 5

Write-Host "== Data di target ==" -ForegroundColor Green
Write-Host "-- OpenEMR Encounter (subject -> Patient/1) --"
(Invoke-RestMethod "http://localhost:8100/openemr/Encounter").entry.resource.subject | ConvertTo-Json -Compress
Write-Host "-- SATUSEHAT Observation (LOINC + IHS) --"
(Invoke-RestMethod "http://localhost:8200/fhir-r4/v1/Observation").entry.resource |
  Select-Object resourceType, @{n="subject";e={$_.subject.reference}},
  @{n="code";e={$_.code.coding[0].code}}, @{n="unit";e={$_.valueQuantity.unit}} | ConvertTo-Json
