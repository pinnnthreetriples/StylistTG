<#
.SYNOPSIS
  StylistTG Dev Environment Launcher
#>

param(
    [switch]$NoBrowser,
    [switch]$OpenBrowser,
    [switch]$NoWait
)

$ScriptDir = $PSScriptRoot
if (-not $ScriptDir) { $ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path }
$ProjectRoot = Split-Path -Parent $ScriptDir

if (-not (Test-Path (Join-Path $ProjectRoot "backend"))) {
    Write-Host ""
    Write-Host "  ERROR: backend/ not found in $ProjectRoot" -ForegroundColor Red
    Write-Host ""
    Read-Host "  Press Enter to exit"
    exit 1
}

$BackendDir  = Join-Path $ProjectRoot "backend"
$LogDir      = Join-Path $BackendDir "logs"
$Timestamp   = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$BackendPort = 8002
$RedisUrl    = "redis://127.0.0.1:6379/0"
$MemuraiExe  = "C:\Tools\Memurai\memurai.exe"
$MemuraiDataDir = "C:\ProgramData\StylistTG\memurai"

if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir -Force | Out-Null }

function Test-TcpPort {
    param(
        [string]$HostName,
        [int]$Port,
        [int]$TimeoutMilliseconds = 1000
    )

    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $connectTask = $client.ConnectAsync($HostName, $Port)
        if (-not $connectTask.Wait($TimeoutMilliseconds)) {
            return $false
        }
        return $client.Connected
    }
    catch {
        return $false
    }
    finally {
        $client.Dispose()
    }
}

function Test-RedisPing {
    param([string]$Url)

    $script = @"
from redis import Redis
try:
    raise SystemExit(0 if Redis.from_url("$Url", socket_connect_timeout=2, socket_timeout=2).ping() else 1)
except Exception:
    raise SystemExit(1)
"@
    $script | python - 2>$null
    return $LASTEXITCODE -eq 0
}

function Stop-ProcessTree {
    param([int]$ProcessId)

    $pending = New-Object System.Collections.Generic.Queue[int]
    $visited = @{}
    $pending.Enqueue($ProcessId)
    $ordered = New-Object System.Collections.Generic.List[int]

    while ($pending.Count -gt 0) {
        $current = $pending.Dequeue()
        if ($visited.ContainsKey($current)) {
            continue
        }
        $visited[$current] = $true
        $ordered.Add($current)

        Get-CimInstance Win32_Process -Filter "ParentProcessId=$current" -ErrorAction SilentlyContinue | ForEach-Object {
            if (-not $visited.ContainsKey($_.ProcessId)) {
                $pending.Enqueue($_.ProcessId)
            }
        }
    }

    for ($i = $ordered.Count - 1; $i -ge 0; $i--) {
        Stop-Process -Id $ordered[$i] -Force -ErrorAction SilentlyContinue
    }
}

function Stop-MatchingProcesses {
    param([string]$CommandLinePattern)

    Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -and $_.CommandLine -match $CommandLinePattern } |
        ForEach-Object { Stop-ProcessTree -ProcessId $_.ProcessId }
}

Write-Host ""
Write-Host "  ============================================" -ForegroundColor Cyan
Write-Host "         StylistTG Dev Environment" -ForegroundColor Cyan
Write-Host "  ============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Project: $ProjectRoot" -ForegroundColor DarkGray
Write-Host ""

# ---- Step 1: Redis via Windows/Memurai ----
$redisStarted = $false
$redisOwnedByScript = $false
$redisWarning = $null
$redisProc = $null
Write-Host "  [1/4] Redis..." -ForegroundColor DarkGray

if ((Test-TcpPort -HostName "127.0.0.1" -Port 6379) -and (Test-RedisPing -Url $RedisUrl)) {
    Write-Host "        OK: Redis already running at localhost:6379" -ForegroundColor Green
    $redisStarted = $true
}
elseif (Test-Path $MemuraiExe) {
    try {
        New-Item -ItemType Directory -Path $MemuraiDataDir -Force | Out-Null
        $memuraiLogOut = Join-Path $LogDir "memurai_$Timestamp.log"
        $memuraiLogErr = Join-Path $LogDir "memurai_err_$Timestamp.log"
        $redisProc = Start-Process -FilePath $MemuraiExe `
            -ArgumentList "--bind", "127.0.0.1", "--port", "6379", "--dir", "$MemuraiDataDir" `
            -WorkingDirectory $MemuraiDataDir `
            -RedirectStandardOutput $memuraiLogOut `
            -RedirectStandardError $memuraiLogErr `
            -PassThru -WindowStyle Hidden

        Start-Sleep -Seconds 2
        if ((-not $redisProc.HasExited) -and (Test-RedisPing -Url $RedisUrl)) {
            Write-Host "        OK: Memurai started at localhost:6379" -ForegroundColor Green
            $redisStarted = $true
            $redisOwnedByScript = $true
        }
        else {
            $redisWarning = "Memurai failed to start. Check log: $memuraiLogErr"
            Write-Host "        WARN: Memurai failed to start" -ForegroundColor Yellow
        }
    }
    catch {
        $redisWarning = "Memurai startup failed: $($_.Exception.Message)"
        Write-Host "        WARN: Memurai startup failed" -ForegroundColor Yellow
    }
}
else {
    $redisWarning = "Memurai not found at $MemuraiExe. Jobs will stay queued."
    Write-Host "        WARN: Memurai not found" -ForegroundColor Yellow
}

if (-not $redisStarted) {
    Write-Host "        Jobs will stay queued until Redis and worker are running." -ForegroundColor Yellow
}

# ---- Step 2: Migrations ----
Write-Host ""
Write-Host "  [2/4] Database migrations..." -ForegroundColor DarkGray

Push-Location $BackendDir
try {
    $null = python -m alembic upgrade head 2>&1
    Write-Host "        OK: Migrations applied" -ForegroundColor Green
}
catch {
    Write-Host "        WARN: Migration error" -ForegroundColor Yellow
}
Pop-Location

# ---- Step 3: Backend ----
Write-Host ""
Write-Host "  [3/4] Backend (FastAPI :$BackendPort)..." -ForegroundColor DarkGray

$backendLogOut = Join-Path $LogDir "backend_$Timestamp.log"
$backendLogErr = Join-Path $LogDir "backend_err_$Timestamp.log"

# Kill stale project backend/worker processes first. Uvicorn --reload uses a
# parent/child process tree, so killing only the socket owner can leave orphans.
Stop-MatchingProcesses "uvicorn app\.main:app.*--port $BackendPort"
Stop-MatchingProcesses "rq\.cli.*worker.*profile_jobs"
Stop-MatchingProcesses "rq\.cli.*worker.*auth_jobs"
Stop-MatchingProcesses "tdlib_job\.py"

# Kill anything on the backend port first
Get-NetTCPConnection -LocalPort $BackendPort -ErrorAction SilentlyContinue | ForEach-Object {
    Stop-ProcessTree -ProcessId $_.OwningProcess
}
Start-Sleep -Milliseconds 500

try {
    $env:REDIS_URL = $RedisUrl
    $backendProc = Start-Process -FilePath "python" `
        -ArgumentList "-m", "uvicorn", "app.main:app", "--reload", "--port", "$BackendPort", "--log-level", "info" `
        -WorkingDirectory $BackendDir `
        -RedirectStandardOutput $backendLogOut `
        -RedirectStandardError $backendLogErr `
        -PassThru -WindowStyle Hidden

    Write-Host "        PID: $($backendProc.Id)" -ForegroundColor DarkGray
}
catch {
    Write-Host "        ERROR: Failed to start backend!" -ForegroundColor Red
    Write-Host "        $($_.Exception.Message)" -ForegroundColor Red
    Read-Host "  Press Enter to exit"
    exit 1
}

Write-Host "        Waiting (TDLib cold start can take ~30s)..." -NoNewline -ForegroundColor DarkGray
$ready = $false
for ($i = 0; $i -lt 45; $i++) {
    Start-Sleep -Milliseconds 1000
    try {
        $h = Invoke-RestMethod -Uri "http://127.0.0.1:$BackendPort/health" -Method GET -TimeoutSec 5 -ErrorAction Stop
        if ($h.status -eq "ok") {
            $ready = $true
            break
        }
    }
    catch { }
    if ($i % 5 -eq 4) { Write-Host "." -NoNewline -ForegroundColor DarkGray }
}
if ($ready) {
    Write-Host " OK!" -ForegroundColor Green
}
else {
    Write-Host ""
    Write-Host "        WARN: Backend not responding after 45s" -ForegroundColor Yellow
    Write-Host "        Check log: $backendLogErr" -ForegroundColor DarkGray
    if (Test-Path $backendLogErr) {
        $errLines = Get-Content $backendLogErr -Tail 5 -ErrorAction SilentlyContinue
        if ($errLines) {
            Write-Host ""
            $errLines | ForEach-Object { Write-Host "        $_" -ForegroundColor Red }
        }
    }
}

# ---- Step 3b: RQ Worker ----
$workerProc = $null
if ($redisStarted) {
    Write-Host ""
    Write-Host "  [3b]  RQ Worker (profile_jobs, auth_jobs)..." -ForegroundColor DarkGray
    $workerLogOut = Join-Path $LogDir "worker_$Timestamp.log"
    $workerLogErr = Join-Path $LogDir "worker_err_$Timestamp.log"
    try {
        $workerProc = Start-Process -FilePath "python" `
            -ArgumentList "-m", "rq.cli", "worker", "profile_jobs", "--url", "$RedisUrl", "--worker-class", "rq.SimpleWorker" `
            -WorkingDirectory $BackendDir `
            -RedirectStandardOutput $workerLogOut `
            -RedirectStandardError $workerLogErr `
            -PassThru -WindowStyle Hidden
        Write-Host "        PID: $($workerProc.Id)" -ForegroundColor DarkGray
        $authWorkerLogOut = Join-Path $LogDir "auth_worker_$Timestamp.log"
        $authWorkerLogErr = Join-Path $LogDir "auth_worker_err_$Timestamp.log"
        $authWorkerProc = Start-Process -FilePath "python" `
            -ArgumentList "-m", "rq.cli", "worker", "auth_jobs", "--url", "$RedisUrl", "--worker-class", "rq.SimpleWorker" `
            -WorkingDirectory $BackendDir `
            -RedirectStandardOutput $authWorkerLogOut `
            -RedirectStandardError $authWorkerLogErr `
            -PassThru -WindowStyle Hidden
        Write-Host "        Auth PID: $($authWorkerProc.Id)" -ForegroundColor DarkGray
        Start-Sleep -Milliseconds 800
        if ($workerProc.HasExited) {
            Write-Host "        WARN: Worker exited immediately" -ForegroundColor Yellow
            if (Test-Path $workerLogErr) {
                Get-Content $workerLogErr -Tail 5 -ErrorAction SilentlyContinue | ForEach-Object {
                    Write-Host "        $_" -ForegroundColor Red
                }
            }
        }
    }
    catch {
        Write-Host "        WARN: Worker failed to start" -ForegroundColor Yellow
    }
}

# ---- Step 4: Frontend ----
Write-Host ""
Write-Host "  [4/4] Frontend (Vite :5173)..." -ForegroundColor DarkGray

$frontendLogOut = Join-Path $LogDir "frontend_$Timestamp.log"
$frontendLogErr = Join-Path $LogDir "frontend_err_$Timestamp.log"

# Kill stale Vite processes before binding the expected port. If Vite keeps
# running, a fresh launch silently moves to 5174 and the browser stays on stale UI.
Stop-MatchingProcesses "StylistTG.*node_modules.*vite"

# Kill anything on port 5173 first
Get-NetTCPConnection -LocalPort 5173 -ErrorAction SilentlyContinue | ForEach-Object {
    Stop-ProcessTree -ProcessId $_.OwningProcess
}

try {
    $frontendProc = Start-Process -FilePath "cmd.exe" `
        -ArgumentList "/c", "npm", "--workspace", "@stylisttg/dashboard", "run", "dev", "--", "--host", "127.0.0.1", "--port", "5173", "--strictPort" `
        -WorkingDirectory $ProjectRoot `
        -RedirectStandardOutput $frontendLogOut `
        -RedirectStandardError $frontendLogErr `
        -PassThru -WindowStyle Hidden
    Write-Host "        PID: $($frontendProc.Id)" -ForegroundColor DarkGray
}
catch {
    Write-Host "        ERROR: Failed to start frontend!" -ForegroundColor Red
    Write-Host "        $($_.Exception.Message)" -ForegroundColor Red
}

Start-Sleep -Seconds 2

# ---- Summary ----
Write-Host ""
Write-Host "  ============================================" -ForegroundColor Cyan
if ($ready -and $redisStarted -and $workerProc -and -not $workerProc.HasExited) {
    Write-Host "  All components started!" -ForegroundColor Green
}
else {
    Write-Host "  Started with warnings" -ForegroundColor Yellow
}
Write-Host ""
Write-Host "    UI:    http://localhost:5173" -ForegroundColor White
Write-Host "    API:   http://localhost:$BackendPort" -ForegroundColor White
Write-Host "    Logs:  backend\logs\" -ForegroundColor DarkGray
if ($redisStarted) {
    Write-Host "    Redis: localhost:6379" -ForegroundColor DarkGray
}
else {
    Write-Host "    Redis: not running (jobs queued)" -ForegroundColor Yellow
    if ($redisWarning) {
        Write-Host "           $redisWarning" -ForegroundColor Yellow
    }
}
Write-Host ""
Write-Host "  ============================================" -ForegroundColor Cyan
Write-Host ""

if ($OpenBrowser -and -not $NoBrowser) {
    Start-Process "http://localhost:5173"
}
else {
    Write-Host "  Browser not opened. Use -OpenBrowser to launch http://localhost:5173." -ForegroundColor DarkGray
    Write-Host ""
}

if ($NoWait) {
    Write-Host "  NoWait enabled; components remain running." -ForegroundColor Yellow
    Write-Host ""
    exit 0
}

Write-Host "  Press Enter to stop all components" -ForegroundColor Yellow
Write-Host ""
Read-Host "  >>>"

# ---- Cleanup ----
Write-Host ""
Write-Host "  Stopping..." -ForegroundColor Yellow

if ($frontendProc -and -not $frontendProc.HasExited) {
    Stop-ProcessTree -ProcessId $frontendProc.Id
    Write-Host "    Stopped: Frontend" -ForegroundColor DarkGray
}
if ($workerProc -and -not $workerProc.HasExited) {
    Stop-ProcessTree -ProcessId $workerProc.Id
    Write-Host "    Stopped: Worker" -ForegroundColor DarkGray
}
if ($backendProc -and -not $backendProc.HasExited) {
    Stop-ProcessTree -ProcessId $backendProc.Id
    Write-Host "    Stopped: Backend" -ForegroundColor DarkGray
}
if ($redisOwnedByScript) {
    if ($redisProc -and -not $redisProc.HasExited) {
        Stop-ProcessTree -ProcessId $redisProc.Id
        Write-Host "    Stopped: Redis" -ForegroundColor DarkGray
    }
}

Write-Host ""
Write-Host "  Done. Logs saved to backend\logs\" -ForegroundColor Green
Write-Host ""
