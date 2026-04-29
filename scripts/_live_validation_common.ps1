Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function New-LiveValidationArtifactDir {
    param(
        [string]$ArtifactsRoot = "artifacts/live-validation",
        [string]$Label = "run"
    )

    $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $path = Join-Path $ArtifactsRoot "$timestamp-$Label"
    New-Item -ItemType Directory -Path $path -Force | Out-Null
    return (Resolve-Path $path).Path
}

function Write-JsonArtifact {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [Parameter(Mandatory = $true)]
        [object]$Value
    )

    $Value | ConvertTo-Json -Depth 10 | Set-Content -Path $Path -Encoding utf8
}

function Invoke-JsonRequest {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Method,
        [Parameter(Mandatory = $true)]
        [string]$Uri,
        [hashtable]$Body
    )

    $requestParams = @{
        Method = $Method
        Uri = $Uri
    }

    if ($null -ne $Body) {
        $requestParams["ContentType"] = "application/json"
        $requestParams["Body"] = $Body | ConvertTo-Json -Depth 10
    }

    try {
        $response = Invoke-WebRequest @requestParams
        $statusCode = [int]$response.StatusCode
        $content = $response.Content
    }
    catch {
        if ($null -eq $_.Exception.Response) {
            throw
        }

        $errorResponse = $_.Exception.Response
        $statusCode = [int]$errorResponse.StatusCode
        $reader = New-Object System.IO.StreamReader($errorResponse.GetResponseStream())
        try {
            $content = $reader.ReadToEnd()
        }
        finally {
            $reader.Dispose()
        }
    }

    $parsedBody = $null
    if ($content) {
        $parsedBody = $content | ConvertFrom-Json
    }

    return [pscustomobject]@{
        status_code = $statusCode
        body = $parsedBody
    }
}

function Save-WorkerLogExcerpt {
    param(
        [string]$WorkerLogPath,
        [string]$DestinationPath,
        [int]$TailLines = 200
    )

    if (-not $WorkerLogPath) {
        return
    }

    if (-not (Test-Path $WorkerLogPath)) {
        "worker log not found: $WorkerLogPath" | Set-Content -Path $DestinationPath -Encoding utf8
        return
    }

    Get-Content -Path $WorkerLogPath -Tail $TailLines | Set-Content -Path $DestinationPath -Encoding utf8
}
