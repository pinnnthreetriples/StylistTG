param(
    [string]$RedisUrl = "redis://127.0.0.1:6379/0",
    [string]$QueueName = "profile_jobs",
    [string]$ArtifactsRoot = "artifacts/live-validation",
    [string]$LogPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. "$PSScriptRoot\_live_validation_common.ps1"

$projectRoot = Split-Path $PSScriptRoot -Parent
$backendRoot = Join-Path $projectRoot "backend"

if (-not $LogPath) {
    $artifactDir = New-LiveValidationArtifactDir -ArtifactsRoot $ArtifactsRoot -Label "worker"
    $LogPath = Join-Path $artifactDir "worker.log"
}

Push-Location $backendRoot
try {
    python -m rq.cli worker $QueueName --url $RedisUrl --worker-class rq.SimpleWorker 2>&1 | Tee-Object -FilePath $LogPath
}
finally {
    Pop-Location
}
