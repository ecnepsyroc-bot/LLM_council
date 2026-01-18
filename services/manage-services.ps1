# LLM Council - Service Management Script
# Provides easy commands for managing the LLM Council services

param(
    [Parameter(Position=0)]
    [ValidateSet("status", "start", "stop", "restart", "logs", "help")]
    [string]$Action = "help"
)

$BackendServiceName = "LLMCouncil-Backend"
$FrontendServiceName = "LLMCouncil-Frontend"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$LogsDir = Join-Path $ProjectRoot "logs"

function Show-Help {
    Write-Host ""
    Write-Host "LLM Council Service Manager" -ForegroundColor Cyan
    Write-Host "===========================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Usage: .\manage-services.ps1 <action>" -ForegroundColor White
    Write-Host ""
    Write-Host "Actions:" -ForegroundColor Yellow
    Write-Host "  status   - Show current status of services"
    Write-Host "  start    - Start both services"
    Write-Host "  stop     - Stop both services"
    Write-Host "  restart  - Restart both services"
    Write-Host "  logs     - Show recent log entries"
    Write-Host "  help     - Show this help message"
    Write-Host ""
    Write-Host "Examples:" -ForegroundColor Yellow
    Write-Host "  .\manage-services.ps1 status"
    Write-Host "  .\manage-services.ps1 restart"
    Write-Host ""
}

function Show-Status {
    Write-Host ""
    Write-Host "Service Status" -ForegroundColor Cyan
    Write-Host "==============" -ForegroundColor Cyan
    Write-Host ""

    $backend = Get-Service -Name $BackendServiceName -ErrorAction SilentlyContinue
    $frontend = Get-Service -Name $FrontendServiceName -ErrorAction SilentlyContinue

    if ($backend) {
        $statusColor = switch ($backend.Status) {
            "Running" { "Green" }
            "Stopped" { "Red" }
            default { "Yellow" }
        }
        Write-Host "Backend:  " -NoNewline
        Write-Host $backend.Status -ForegroundColor $statusColor
    } else {
        Write-Host "Backend:  " -NoNewline
        Write-Host "Not Installed" -ForegroundColor Gray
    }

    if ($frontend) {
        $statusColor = switch ($frontend.Status) {
            "Running" { "Green" }
            "Stopped" { "Red" }
            default { "Yellow" }
        }
        Write-Host "Frontend: " -NoNewline
        Write-Host $frontend.Status -ForegroundColor $statusColor
    } else {
        Write-Host "Frontend: " -NoNewline
        Write-Host "Not Installed" -ForegroundColor Gray
    }

    Write-Host ""

    if ($backend -and $backend.Status -eq "Running") {
        Write-Host "Backend API:  http://localhost:8001" -ForegroundColor Gray
    }
    if ($frontend -and $frontend.Status -eq "Running") {
        Write-Host "Frontend UI:  http://localhost:5173" -ForegroundColor Gray
    }
    Write-Host ""
}

function Start-Services {
    Write-Host ""
    Write-Host "Starting Services..." -ForegroundColor Cyan

    $backend = Get-Service -Name $BackendServiceName -ErrorAction SilentlyContinue
    $frontend = Get-Service -Name $FrontendServiceName -ErrorAction SilentlyContinue

    if (-not $backend -or -not $frontend) {
        Write-Host "Services not installed. Run install-services.ps1 first." -ForegroundColor Red
        return
    }

    if ($backend.Status -ne "Running") {
        Write-Host "  Starting Backend..." -ForegroundColor Yellow
        Start-Service -Name $BackendServiceName
        Start-Sleep -Seconds 2
    } else {
        Write-Host "  Backend already running" -ForegroundColor Gray
    }

    if ($frontend.Status -ne "Running") {
        Write-Host "  Starting Frontend..." -ForegroundColor Yellow
        Start-Service -Name $FrontendServiceName
        Start-Sleep -Seconds 2
    } else {
        Write-Host "  Frontend already running" -ForegroundColor Gray
    }

    Show-Status
}

function Stop-Services {
    Write-Host ""
    Write-Host "Stopping Services..." -ForegroundColor Cyan

    $frontend = Get-Service -Name $FrontendServiceName -ErrorAction SilentlyContinue
    $backend = Get-Service -Name $BackendServiceName -ErrorAction SilentlyContinue

    if ($frontend -and $frontend.Status -eq "Running") {
        Write-Host "  Stopping Frontend..." -ForegroundColor Yellow
        Stop-Service -Name $FrontendServiceName -Force
    }

    if ($backend -and $backend.Status -eq "Running") {
        Write-Host "  Stopping Backend..." -ForegroundColor Yellow
        Stop-Service -Name $BackendServiceName -Force
    }

    Start-Sleep -Seconds 2
    Show-Status
}

function Restart-Services {
    Stop-Services
    Start-Sleep -Seconds 1
    Start-Services
}

function Show-Logs {
    Write-Host ""
    Write-Host "Recent Logs" -ForegroundColor Cyan
    Write-Host "===========" -ForegroundColor Cyan

    $backendLog = Join-Path $LogsDir "backend.log"
    $frontendLog = Join-Path $LogsDir "frontend.log"
    $backendErrorLog = Join-Path $LogsDir "backend-error.log"
    $frontendErrorLog = Join-Path $LogsDir "frontend-error.log"

    if (Test-Path $backendLog) {
        Write-Host ""
        Write-Host "Backend Log (last 20 lines):" -ForegroundColor Yellow
        Get-Content $backendLog -Tail 20
    }

    if (Test-Path $backendErrorLog) {
        $errorContent = Get-Content $backendErrorLog -Tail 10 -ErrorAction SilentlyContinue
        if ($errorContent) {
            Write-Host ""
            Write-Host "Backend Errors (last 10 lines):" -ForegroundColor Red
            $errorContent
        }
    }

    if (Test-Path $frontendLog) {
        Write-Host ""
        Write-Host "Frontend Log (last 20 lines):" -ForegroundColor Yellow
        Get-Content $frontendLog -Tail 20
    }

    if (Test-Path $frontendErrorLog) {
        $errorContent = Get-Content $frontendErrorLog -Tail 10 -ErrorAction SilentlyContinue
        if ($errorContent) {
            Write-Host ""
            Write-Host "Frontend Errors (last 10 lines):" -ForegroundColor Red
            $errorContent
        }
    }

    Write-Host ""
    Write-Host "Log files location: $LogsDir" -ForegroundColor Gray
    Write-Host ""
}

# Main execution
switch ($Action) {
    "status" { Show-Status }
    "start" { Start-Services }
    "stop" { Stop-Services }
    "restart" { Restart-Services }
    "logs" { Show-Logs }
    "help" { Show-Help }
    default { Show-Help }
}
