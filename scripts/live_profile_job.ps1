param(
    [Parameter(Mandatory = $true)]
    [string]$AccountId,
    [string]$PhotoPath,
    [string]$Name,
    [string]$Bio,
    [string]$Username,
    [string]$ApiBaseUrl = "http://127.0.0.1:8000",
    [string]$ArtifactsRoot = "artifacts/live-validation",
    [string]$ArtifactDir,
    [string]$WorkerLogPath,
    [int]$PollSeconds = 60,
    [int]$PollIntervalSeconds = 2
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. "$PSScriptRoot\_live_validation_common.ps1"

if (-not $ArtifactDir) {
    $ArtifactDir = New-LiveValidationArtifactDir -ArtifactsRoot $ArtifactsRoot -Label "profile"
}

Write-JsonArtifact -Path (Join-Path $ArtifactDir "ready.json") -Value (Invoke-JsonRequest -Method Get -Uri "$ApiBaseUrl/ready")
Write-JsonArtifact -Path (Join-Path $ArtifactDir "diagnostics-runtime.json") -Value (Invoke-JsonRequest -Method Get -Uri "$ApiBaseUrl/diagnostics/runtime")
Write-JsonArtifact -Path (Join-Path $ArtifactDir "diagnostics-live-preflight.json") -Value (Invoke-JsonRequest -Method Get -Uri "$ApiBaseUrl/diagnostics/live-preflight")
$runtimeRefresh = (Invoke-JsonRequest -Method Post -Uri "$ApiBaseUrl/api/accounts/$AccountId/refresh-runtime").body
$accountDiagnostics = (Invoke-JsonRequest -Method Get -Uri "$ApiBaseUrl/api/accounts/$AccountId/runtime-diagnostics").body
Write-JsonArtifact -Path (Join-Path $ArtifactDir "runtime-refresh.json") -Value $runtimeRefresh
Write-JsonArtifact -Path (Join-Path $ArtifactDir "runtime-diagnostics.json") -Value $accountDiagnostics

$jobPayload = @{ account_id = $AccountId }
if ($Name) { $jobPayload.name = $Name }
if ($Bio) { $jobPayload.bio = $Bio }
if ($Username) { $jobPayload.username = $Username }

if ($PhotoPath) {
    $resolvedPhotoPath = (Resolve-Path $PhotoPath).Path
    $uploadResponse = curl.exe -sS -X POST "$ApiBaseUrl/api/assets/profile-photo" -F "file=@$resolvedPhotoPath;type=image/jpeg"
    $asset = $uploadResponse | ConvertFrom-Json
    Write-JsonArtifact -Path (Join-Path $ArtifactDir "asset-upload.json") -Value $asset
    $jobPayload.photo_asset_id = $asset.id
}

Write-JsonArtifact -Path (Join-Path $ArtifactDir "job-payload.json") -Value $jobPayload
$job = (Invoke-JsonRequest -Method Post -Uri "$ApiBaseUrl/api/jobs/profile" -Body $jobPayload).body
Write-JsonArtifact -Path (Join-Path $ArtifactDir "job-create.json") -Value $job

$deadline = (Get-Date).AddSeconds($PollSeconds)
$terminalStates = @("completed", "partially_completed", "failed", "manual_intervention_needed", "canceled", "dedup_blocked")
$latestJob = $job

while ((Get-Date) -lt $deadline) {
    $latestJob = (Invoke-JsonRequest -Method Get -Uri "$ApiBaseUrl/api/jobs/$($job.id)").body
    if ($terminalStates -contains $latestJob.job_state) {
        break
    }
    Start-Sleep -Seconds $PollIntervalSeconds
}

$steps = (Invoke-JsonRequest -Method Get -Uri "$ApiBaseUrl/api/jobs/$($job.id)/steps").body
Write-JsonArtifact -Path (Join-Path $ArtifactDir "job-final.json") -Value $latestJob
Write-JsonArtifact -Path (Join-Path $ArtifactDir "job-steps.json") -Value $steps
Save-WorkerLogExcerpt -WorkerLogPath $WorkerLogPath -DestinationPath (Join-Path $ArtifactDir "worker-log-excerpt.txt")

Write-JsonArtifact -Path (Join-Path $ArtifactDir "summary.json") -Value @{
    account_id = $AccountId
    job_id = $job.id
    artifact_dir = $ArtifactDir
    terminal_job_state = $latestJob.job_state
}

Write-Output "Artifacts: $ArtifactDir"
