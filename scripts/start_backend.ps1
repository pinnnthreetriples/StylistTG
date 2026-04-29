param(
    [string]$Host = "127.0.0.1",
    [int]$Port = 8000,
    [string]$ArtifactsRoot = "artifacts/live-validation",
    [string]$LogPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. "$PSScriptRoot\_live_validation_common.ps1"

$projectRoot = Split-Path $PSScriptRoot -Parent
$backendRoot = Join-Path $projectRoot "backend"

if (-not $LogPath) {
    $artifactDir = New-LiveValidationArtifactDir -ArtifactsRoot $ArtifactsRoot -Label "backend"
    $LogPath = Join-Path $artifactDir "backend.log"
}

Push-Location $backendRoot
try {
    python -m uvicorn app.main:app --host $Host --port $Port --reload 2>&1 | Tee-Object -FilePath $LogPath
}
finally {
    Pop-Location
}
