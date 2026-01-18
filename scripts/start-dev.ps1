# start-dev.ps1 - Start development environment

param(
    [switch]$WithTunnel,      # Start SSH tunnel to Cambium
    [switch]$BackendOnly,     # Only start backend
    [switch]$FrontendOnly,    # Only start frontend
    [switch]$Force            # Kill existing processes on ports
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot

Write-Host "`n=== Starting Dejavara Dev Environment ===" -ForegroundColor Cyan
Write-Host "Project: $ProjectRoot`n"

function Stop-PortProcess {
    param([int]$Port)

    $connection = netstat -ano | Select-String ":$Port\s+.*LISTENING"
    if ($connection) {
        $procId = ($connection.Line.Trim() -split '\s+')[-1]
        Write-Host "Killing process on port $Port (PID: $procId)..." -ForegroundColor Yellow
        taskkill /PID $procId /F 2>$null
        Start-Sleep -Seconds 1
    }
}

function Test-Port {
    param([int]$Port)
    $connection = netstat -ano | Select-String ":$Port\s+.*LISTENING"
    return $null -ne $connection
}

# Check for port conflicts
$backendPort = 8001
$frontendPort = 5173

if (-not $FrontendOnly) {
    if (Test-Port $backendPort) {
        if ($Force) {
            Stop-PortProcess $backendPort
        } else {
            Write-Host "[WARNING] Port $backendPort already in use. Use -Force to kill." -ForegroundColor Yellow
        }
    }
}

if (-not $BackendOnly) {
    if (Test-Port $frontendPort) {
        if ($Force) {
            Stop-PortProcess $frontendPort
        } else {
            Write-Host "[WARNING] Port $frontendPort already in use. Use -Force to kill." -ForegroundColor Yellow
        }
    }
}

# Start SSH tunnel if requested
if ($WithTunnel) {
    Write-Host "`n[1/3] Starting SSH tunnel to Cambium (localhost:5433 -> Cambium:5432)..." -ForegroundColor Cyan

    # Check if tunnel already exists
    if (Test-Port 5433) {
        Write-Host "  SSH tunnel already active on port 5433" -ForegroundColor Green
    } else {
        Start-Process -FilePath "ssh" -ArgumentList "-L", "5433:localhost:5432", "cambium", "-N" -WindowStyle Hidden
        Start-Sleep -Seconds 2

        if (Test-Port 5433) {
            Write-Host "  SSH tunnel started successfully" -ForegroundColor Green
        } else {
            Write-Host "  [ERROR] Failed to start SSH tunnel" -ForegroundColor Red
        }
    }
}

# Start backend
if (-not $FrontendOnly) {
    Write-Host "`n[2/3] Starting LLM Council Backend (port $backendPort)..." -ForegroundColor Cyan

    Push-Location $ProjectRoot
    $env:BYPASS_AUTH = "true"
    Start-Process -FilePath "python" -ArgumentList "-m", "backend.main" -WindowStyle Minimized
    Pop-Location

    Start-Sleep -Seconds 2

    if (Test-Port $backendPort) {
        Write-Host "  Backend started: http://localhost:$backendPort" -ForegroundColor Green
        Write-Host "  Health check: http://localhost:$backendPort/health" -ForegroundColor DarkGray
    } else {
        Write-Host "  [ERROR] Backend failed to start" -ForegroundColor Red
    }
}

# Start frontend
if (-not $BackendOnly) {
    Write-Host "`n[3/3] Starting LLM Council Frontend (port $frontendPort)..." -ForegroundColor Cyan

    Push-Location "$ProjectRoot\frontend"
    Start-Process -FilePath "npm" -ArgumentList "run", "dev" -WindowStyle Minimized
    Pop-Location

    Start-Sleep -Seconds 3

    # Check 5173 or 5174
    $actualPort = if (Test-Port 5173) { 5173 } elseif (Test-Port 5174) { 5174 } else { $null }

    if ($actualPort) {
        Write-Host "  Frontend started: http://localhost:$actualPort" -ForegroundColor Green
    } else {
        Write-Host "  [ERROR] Frontend failed to start" -ForegroundColor Red
    }
}

Write-Host "`n=== Dev Environment Ready ===" -ForegroundColor Green
Write-Host ""

# Show status
& "$PSScriptRoot\check-ports.ps1"
