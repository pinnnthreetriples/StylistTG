param(
    [string]$ApiBaseUrl = "http://127.0.0.1:8000",
    [string]$ArtifactsRoot = "artifacts/live-validation",
    [string]$ArtifactDir,
    [string]$AccountId,
    [string]$JobId,
    [string]$WorkerLogPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. "$PSScriptRoot\_live_validation_common.ps1"

if (-not $ArtifactDir) {
    $ArtifactDir = New-LiveValidationArtifactDir -ArtifactsRoot $ArtifactsRoot -Label "capture"
}

$ready = Invoke-JsonRequest -Method Get -Uri "$ApiBaseUrl/ready"
$runtimeDiagnostics = Invoke-JsonRequest -Method Get -Uri "$ApiBaseUrl/diagnostics/runtime"
$livePreflight = Invoke-JsonRequest -Method Get -Uri "$ApiBaseUrl/diagnostics/live-preflight"

Write-JsonArtifact -Path (Join-Path $ArtifactDir "ready.json") -Value $ready
Write-JsonArtifact -Path (Join-Path $ArtifactDir "diagnostics-runtime.json") -Value $runtimeDiagnostics
Write-JsonArtifact -Path (Join-Path $ArtifactDir "diagnostics-live-preflight.json") -Value $livePreflight

if ($AccountId) {
    Write-JsonArtifact -Path (Join-Path $ArtifactDir "auth-state.json") -Value (Invoke-JsonRequest -Method Get -Uri "$ApiBaseUrl/api/accounts/$AccountId/auth-state")
    Write-JsonArtifact -Path (Join-Path $ArtifactDir "runtime-diagnostics.json") -Value (Invoke-JsonRequest -Method Get -Uri "$ApiBaseUrl/api/accounts/$AccountId/runtime-diagnostics")
}

if ($JobId) {
    Write-JsonArtifact -Path (Join-Path $ArtifactDir "job.json") -Value (Invoke-JsonRequest -Method Get -Uri "$ApiBaseUrl/api/jobs/$JobId")
    Write-JsonArtifact -Path (Join-Path $ArtifactDir "job-steps.json") -Value (Invoke-JsonRequest -Method Get -Uri "$ApiBaseUrl/api/jobs/$JobId/steps")
}

Save-WorkerLogExcerpt -WorkerLogPath $WorkerLogPath -DestinationPath (Join-Path $ArtifactDir "worker-log-excerpt.txt")
Write-Output $ArtifactDir
