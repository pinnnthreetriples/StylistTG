#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Local quality gate wrapper (PowerShell).

.DESCRIPTION
    Runs backend/scripts/check.py with the same arguments. Use this from a
    Windows terminal as a more discoverable entry point than `python scripts/check.py`.

.EXAMPLE
    pwsh backend/scripts/check.ps1                  # full gate
    pwsh backend/scripts/check.ps1 -Fast            # skip slow checks
    pwsh backend/scripts/check.ps1 -Only ruff       # only specific checks
#>
[CmdletBinding()]
param(
    [switch]$Fast,
    [string[]]$Skip = @(),
    [string[]]$Only = @(),
    [switch]$Verbose
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = Split-Path -Parent $scriptDir

$pythonArgs = @("scripts/check.py")
if ($Fast)     { $pythonArgs += "--fast" }
if ($Skip)     { $pythonArgs += @("--skip") + $Skip }
if ($Only)     { $pythonArgs += @("--only") + $Only }
if ($Verbose)  { $pythonArgs += "--verbose" }

Push-Location $backendDir
try {
    python @pythonArgs
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
