<#
.SYNOPSIS
  One-command launcher for a fully local, isolated Presentation Mode
  rehearsal -- fresh local SQLite database, local backend, local frontend.

.DESCRIPTION
  Never touches backend/.env, frontend/.env.local, or the real production
  Railway/Vercel deployment. DATABASE_URL and NEXT_PUBLIC_API_URL are
  overridden only as process-level environment variables for the two
  processes this script starts, exactly the way this was validated
  manually before being scripted here -- see
  frontend/docs/ai-usage/feature-demo.md.

  Run from anywhere; paths are resolved relative to this script's own
  location, not the caller's current directory.

.PARAMETER SkipSeed
  Skip pre-seeding ADF Farm Solutions. Useful for a quick restart when
  you've already confirmed the pre-seed landed correctly and just want
  the servers back up.
#>
param(
    [switch]$SkipSeed
)

$ErrorActionPreference = 'Stop'

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot '..\..')
$BackendDir = Join-Path $RepoRoot 'backend'
$FrontendDir = Join-Path $RepoRoot 'frontend'
$BackendPort = 8010
$FrontendPort = 3000
$BackendUrl = "http://127.0.0.1:$BackendPort"
$FrontendUrl = "http://localhost:$FrontendPort"
$LocalDbPath = Join-Path $BackendDir 'local_demo.db'

function Stop-ProcessOnPort {
    <#
    Kills whatever is LISTENing on a given local port, if anything. Every
    run of this script starts brand-new backend/frontend windows via
    Start-Process without tracking their PIDs anywhere -- so a previous
    rehearsal's windows (left open, or closed in a way that didn't kill the
    child process) are exactly what caused both the port-8010 bind failure
    and the locked-local_demo.db failure seen while building this. Calling
    this for both ports FIRST, before anything else, is what makes it safe
    to just re-run this same script over and over between rehearsals
    instead of needing a separate stop script or manual Task Manager
    cleanup every time.
    #>
    param([int]$Port)

    $conns = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if (-not $conns) { return }
    $pids = $conns | Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($procId in $pids) {
        Write-Host "  Port $Port is in use by PID $procId (leftover from a previous run) -- stopping it..." -ForegroundColor Yellow
        Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Milliseconds 500
}

Write-Host ''
Write-Host '=== Senus Board -- Local Demo Launcher ===' -ForegroundColor Cyan
Write-Host 'Fully isolated from production: fresh local SQLite DB, local backend, local frontend.' -ForegroundColor Cyan
Write-Host 'backend/.env and frontend/.env.local are never read or written by this script.' -ForegroundColor Cyan
Write-Host ''

Write-Host 'Clearing any previous local demo run...' -ForegroundColor Cyan
Stop-ProcessOnPort -Port $BackendPort
Stop-ProcessOnPort -Port $FrontendPort

# Fresh start every run, on purpose -- rehearse as many times as you want
# without worrying about duplicate-upload conflicts from a previous run's
# demo uploads (see backend/scripts/local_demo_seed.py). The port-clearing
# step above handles the common case; this retry covers the rare case
# where the file is still momentarily locked right after that process
# exits, rather than hard-failing the whole launch over a timing race.
if (Test-Path $LocalDbPath) {
    Write-Host "Removing previous local_demo.db for a clean run..." -ForegroundColor Yellow
    try {
        Remove-Item $LocalDbPath -Force -ErrorAction Stop
    } catch {
        Write-Host "  Still locked -- waiting 2s and retrying once..." -ForegroundColor Yellow
        Start-Sleep -Seconds 2
        try {
            Remove-Item $LocalDbPath -Force -ErrorAction Stop
        } catch {
            Write-Host "Still locked. Close any other window/process still running a previous local demo backend, then re-run this script." -ForegroundColor Red
            Write-Host "(Task Manager -> look for a stray python.exe from backend\.venv\Scripts\python.exe)" -ForegroundColor Red
            exit 1
        }
    }
}

# --- Backend ---------------------------------------------------------------
Write-Host "Starting local backend on $BackendUrl ..." -ForegroundColor Cyan
$backendProcess = Start-Process powershell -PassThru -ArgumentList @(
    '-NoExit', '-Command',
    "Set-Location '$BackendDir'; " +
    "`$env:DATABASE_URL = 'sqlite+aiosqlite:///./local_demo.db'; " +
    "`$env:LOCAL_DEMO_BACKEND_PORT = '$BackendPort'; " +
    "python scripts/local_demo_server.py"
)

$deadline = (Get-Date).AddSeconds(30)
$backendReady = $false
while ((Get-Date) -lt $deadline) {
    try {
        Invoke-WebRequest -Uri "$BackendUrl/docs" -UseBasicParsing -TimeoutSec 2 | Out-Null
        $backendReady = $true
        break
    } catch {
        Start-Sleep -Milliseconds 500
    }
}
if (-not $backendReady) {
    Write-Host "Backend did not respond within 30s -- check the backend window for errors." -ForegroundColor Red
    exit 1
}
Write-Host "Backend is up." -ForegroundColor Green

# --- Pre-seed ----------------------------------------------------------------
if (-not $SkipSeed) {
    Write-Host ''
    Write-Host 'Pre-seeding the HY2026 half-year PR (Presentation Mode uploads and merges the other two filings live)...' -ForegroundColor Cyan
    Push-Location $BackendDir
    python scripts/local_demo_seed.py
    Pop-Location
}

# --- Frontend ----------------------------------------------------------------
Write-Host ''
Write-Host "Starting local frontend on $FrontendUrl ..." -ForegroundColor Cyan
$frontendProcess = Start-Process powershell -PassThru -ArgumentList @(
    '-NoExit', '-Command',
    "Set-Location '$FrontendDir'; " +
    "`$env:NEXT_PUBLIC_API_URL = '$BackendUrl'; " +
    "npm run dev"
)

$deadline = (Get-Date).AddSeconds(60)
$frontendReady = $false
while ((Get-Date) -lt $deadline) {
    try {
        Invoke-WebRequest -Uri $FrontendUrl -UseBasicParsing -TimeoutSec 2 | Out-Null
        $frontendReady = $true
        break
    } catch {
        Start-Sleep -Milliseconds 500
    }
}
if (-not $frontendReady) {
    Write-Host "Frontend did not respond within 60s -- check the frontend window for errors." -ForegroundColor Red
    exit 1
}
Write-Host "Frontend is up." -ForegroundColor Green

Write-Host ''
Write-Host '=== Ready ===' -ForegroundColor Green
Write-Host "Open $FrontendUrl and click Present." -ForegroundColor Green
Write-Host "Backend window PID $($backendProcess.Id), frontend window PID $($frontendProcess.Id) -- close either window (or Ctrl+C inside it) to stop it." -ForegroundColor Gray
Write-Host "Nothing here touched backend/.env, frontend/.env.local, or production. Delete backend/local_demo.db afterward if you want to fully reset." -ForegroundColor Gray
Write-Host ''
