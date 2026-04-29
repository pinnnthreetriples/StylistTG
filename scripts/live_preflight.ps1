param(
    [string]$ArtifactsRoot = "artifacts/live-validation",
    [string]$ArtifactDir
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. "$PSScriptRoot\_live_validation_common.ps1"

$projectRoot = Split-Path $PSScriptRoot -Parent
$backendRoot = Join-Path $projectRoot "backend"

if (-not $ArtifactDir) {
    $ArtifactDir = New-LiveValidationArtifactDir -ArtifactsRoot $ArtifactsRoot -Label "preflight"
}

Push-Location $backendRoot
try {
    $output = python -m app.tools.live_preflight 2>&1
    $output | Set-Content -Path (Join-Path $ArtifactDir "live-preflight-cli.txt") -Encoding utf8
    $output
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}
finally {
    Pop-Location
}
