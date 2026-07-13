<#
.SYNOPSIS
  Stops the local demo backend/frontend (if running) and deletes
  local_demo.db -- for when you're done rehearsing and want a clean slate
  without immediately starting another run. run.ps1 also does this
  automatically at the start of every run, so this is optional.
#>

$BackendDir = Resolve-Path (Join-Path $PSScriptRoot '..\..\backend')
$LocalDbPath = Join-Path $BackendDir 'local_demo.db'
$BackendPort = 8010
$FrontendPort = 3000

function Stop-ProcessOnPort {
    param([int]$Port)
    $conns = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if (-not $conns) { return }
    foreach ($procId in ($conns | Select-Object -ExpandProperty OwningProcess -Unique)) {
        Write-Host "Stopping PID $procId on port $Port..." -ForegroundColor Yellow
        Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
    }
}

Stop-ProcessOnPort -Port $BackendPort
Stop-ProcessOnPort -Port $FrontendPort
Start-Sleep -Milliseconds 500

if (Test-Path $LocalDbPath) {
    Remove-Item $LocalDbPath -Force -ErrorAction SilentlyContinue
    Write-Host "Removed local_demo.db." -ForegroundColor Green
}

Write-Host "Local demo stopped and cleared. Production was never touched." -ForegroundColor Green
