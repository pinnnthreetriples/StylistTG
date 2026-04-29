param(
    [Parameter(Mandatory = $true)]
    [string]$PhoneNumber,
    [string]$Code,
    [string]$AccountId,
    [string]$ApiBaseUrl = "http://127.0.0.1:8000",
    [string]$ArtifactsRoot = "artifacts/live-validation",
    [string]$ArtifactDir
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. "$PSScriptRoot\_live_validation_common.ps1"

if (-not $ArtifactDir) {
    $ArtifactDir = New-LiveValidationArtifactDir -ArtifactsRoot $ArtifactsRoot -Label "auth"
}

Write-JsonArtifact -Path (Join-Path $ArtifactDir "ready.json") -Value (Invoke-JsonRequest -Method Get -Uri "$ApiBaseUrl/ready")
Write-JsonArtifact -Path (Join-Path $ArtifactDir "diagnostics-runtime.json") -Value (Invoke-JsonRequest -Method Get -Uri "$ApiBaseUrl/diagnostics/runtime")
Write-JsonArtifact -Path (Join-Path $ArtifactDir "diagnostics-live-preflight.json") -Value (Invoke-JsonRequest -Method Get -Uri "$ApiBaseUrl/diagnostics/live-preflight")

if (-not $AccountId) {
    $otpStartResponse = Invoke-JsonRequest -Method Post -Uri "$ApiBaseUrl/api/auth/otp/start" -Body @{ phone_number = $PhoneNumber }
    $otpStart = $otpStartResponse.body
    Write-JsonArtifact -Path (Join-Path $ArtifactDir "otp-start.json") -Value $otpStart
    $AccountId = $otpStart.account_id
}

if (-not $Code) {
    Write-Output "OTP started. Enter the code from Telegram and re-run with -AccountId $AccountId -Code <code>."
    Write-Output "Artifacts: $ArtifactDir"
    exit 0
}

$otpConfirm = (Invoke-JsonRequest -Method Post -Uri "$ApiBaseUrl/api/auth/otp/confirm" -Body @{ account_id = $AccountId; code = $Code }).body
$runtimeRefresh = (Invoke-JsonRequest -Method Post -Uri "$ApiBaseUrl/api/accounts/$AccountId/refresh-runtime").body
$authState = (Invoke-JsonRequest -Method Get -Uri "$ApiBaseUrl/api/accounts/$AccountId/auth-state").body
$runtimeDiagnostics = (Invoke-JsonRequest -Method Get -Uri "$ApiBaseUrl/api/accounts/$AccountId/runtime-diagnostics").body

Write-JsonArtifact -Path (Join-Path $ArtifactDir "otp-confirm.json") -Value $otpConfirm
Write-JsonArtifact -Path (Join-Path $ArtifactDir "runtime-refresh.json") -Value $runtimeRefresh
Write-JsonArtifact -Path (Join-Path $ArtifactDir "auth-state.json") -Value $authState
Write-JsonArtifact -Path (Join-Path $ArtifactDir "runtime-diagnostics.json") -Value $runtimeDiagnostics

Write-JsonArtifact -Path (Join-Path $ArtifactDir "summary.json") -Value @{
    account_id = $AccountId
    artifact_dir = $ArtifactDir
    orchestration_state = $runtimeRefresh.orchestration_state
    runtime_health = $runtimeRefresh.runtime_health
}

Write-Output "Artifacts: $ArtifactDir"
