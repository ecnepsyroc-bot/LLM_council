# LLM Council - Windows Service Installation Script
# This script installs the backend and frontend as Windows services using NSSM
# Run as Administrator

param(
    [switch]$Uninstall,
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot)
)

$ErrorActionPreference = "Stop"

# Service configuration
$BackendServiceName = "LLMCouncil-Backend"
$FrontendServiceName = "LLMCouncil-Frontend"
$NssmPath = Join-Path $PSScriptRoot "nssm.exe"
$NssmUrl = "https://nssm.cc/release/nssm-2.24.zip"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  LLM Council Service Manager" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check for admin rights
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")
if (-not $isAdmin) {
    Write-Host "ERROR: This script requires Administrator privileges." -ForegroundColor Red
    Write-Host "Please run PowerShell as Administrator and try again." -ForegroundColor Yellow
    exit 1
}

# Download NSSM if not present
function Get-NSSM {
    if (Test-Path $NssmPath) {
        Write-Host "NSSM found at $NssmPath" -ForegroundColor Green
        return
    }

    Write-Host "Downloading NSSM (Non-Sucking Service Manager)..." -ForegroundColor Yellow
    $zipPath = Join-Path $env:TEMP "nssm.zip"
    $extractPath = Join-Path $env:TEMP "nssm-extract"

    try {
        Invoke-WebRequest -Uri $NssmUrl -OutFile $zipPath -UseBasicParsing
        Expand-Archive -Path $zipPath -DestinationPath $extractPath -Force

        # Find the 64-bit executable
        $nssmExe = Get-ChildItem -Path $extractPath -Recurse -Filter "nssm.exe" |
            Where-Object { $_.Directory.Name -eq "win64" } |
            Select-Object -First 1

        if ($nssmExe) {
            Copy-Item $nssmExe.FullName $NssmPath
            Write-Host "NSSM downloaded successfully" -ForegroundColor Green
        } else {
            throw "Could not find nssm.exe in downloaded archive"
        }
    }
    finally {
        Remove-Item $zipPath -ErrorAction SilentlyContinue
        Remove-Item $extractPath -Recurse -ErrorAction SilentlyContinue
    }
}

function Install-BackendService {
    Write-Host ""
    Write-Host "Installing Backend Service..." -ForegroundColor Cyan

    # Find Python
    $pythonPath = (Get-Command python -ErrorAction SilentlyContinue).Source
    if (-not $pythonPath) {
        $pythonPath = (Get-Command python3 -ErrorAction SilentlyContinue).Source
    }
    if (-not $pythonPath) {
        Write-Host "ERROR: Python not found in PATH" -ForegroundColor Red
        return $false
    }

    # Remove existing service if present
    $existingService = Get-Service -Name $BackendServiceName -ErrorAction SilentlyContinue
    if ($existingService) {
        Write-Host "  Removing existing service..." -ForegroundColor Yellow
        & $NssmPath stop $BackendServiceName 2>$null
        & $NssmPath remove $BackendServiceName confirm 2>$null
        Start-Sleep -Seconds 2
    }

    # Install service
    & $NssmPath install $BackendServiceName $pythonPath "-m" "backend.main"
    & $NssmPath set $BackendServiceName AppDirectory $ProjectRoot
    & $NssmPath set $BackendServiceName DisplayName "LLM Council Backend"
    & $NssmPath set $BackendServiceName Description "LLM Council Backend API Server (FastAPI on port 8001)"
    & $NssmPath set $BackendServiceName Start SERVICE_AUTO_START
    & $NssmPath set $BackendServiceName AppStdout (Join-Path $ProjectRoot "logs\backend.log")
    & $NssmPath set $BackendServiceName AppStderr (Join-Path $ProjectRoot "logs\backend-error.log")
    & $NssmPath set $BackendServiceName AppRotateFiles 1
    & $NssmPath set $BackendServiceName AppRotateBytes 1048576

    Write-Host "  Backend service installed" -ForegroundColor Green
    return $true
}

function Install-FrontendService {
    Write-Host ""
    Write-Host "Installing Frontend Service..." -ForegroundColor Cyan

    # Find npm
    $npmPath = (Get-Command npm -ErrorAction SilentlyContinue).Source
    if (-not $npmPath) {
        Write-Host "ERROR: npm not found in PATH" -ForegroundColor Red
        return $false
    }

    # Get the npm.cmd path (npm is a shell script, we need the cmd)
    $npmCmd = Join-Path (Split-Path $npmPath) "npm.cmd"
    if (-not (Test-Path $npmCmd)) {
        $npmCmd = $npmPath
    }

    $frontendDir = Join-Path $ProjectRoot "frontend"

    # Remove existing service if present
    $existingService = Get-Service -Name $FrontendServiceName -ErrorAction SilentlyContinue
    if ($existingService) {
        Write-Host "  Removing existing service..." -ForegroundColor Yellow
        & $NssmPath stop $FrontendServiceName 2>$null
        & $NssmPath remove $FrontendServiceName confirm 2>$null
        Start-Sleep -Seconds 2
    }

    # Install service
    & $NssmPath install $FrontendServiceName $npmCmd "run" "dev"
    & $NssmPath set $FrontendServiceName AppDirectory $frontendDir
    & $NssmPath set $FrontendServiceName DisplayName "LLM Council Frontend"
    & $NssmPath set $FrontendServiceName Description "LLM Council Frontend Dev Server (Vite on port 5173)"
    & $NssmPath set $FrontendServiceName Start SERVICE_AUTO_START
    & $NssmPath set $FrontendServiceName DependOnService $BackendServiceName
    & $NssmPath set $FrontendServiceName AppStdout (Join-Path $ProjectRoot "logs\frontend.log")
    & $NssmPath set $FrontendServiceName AppStderr (Join-Path $ProjectRoot "logs\frontend-error.log")
    & $NssmPath set $FrontendServiceName AppRotateFiles 1
    & $NssmPath set $FrontendServiceName AppRotateBytes 1048576

    Write-Host "  Frontend service installed" -ForegroundColor Green
    return $true
}

function Uninstall-Services {
    Write-Host ""
    Write-Host "Uninstalling LLM Council Services..." -ForegroundColor Cyan

    # Stop and remove frontend
    $frontendService = Get-Service -Name $FrontendServiceName -ErrorAction SilentlyContinue
    if ($frontendService) {
        Write-Host "  Stopping $FrontendServiceName..." -ForegroundColor Yellow
        & $NssmPath stop $FrontendServiceName 2>$null
        Write-Host "  Removing $FrontendServiceName..." -ForegroundColor Yellow
        & $NssmPath remove $FrontendServiceName confirm 2>$null
        Write-Host "  Frontend service removed" -ForegroundColor Green
    } else {
        Write-Host "  Frontend service not found" -ForegroundColor Gray
    }

    # Stop and remove backend
    $backendService = Get-Service -Name $BackendServiceName -ErrorAction SilentlyContinue
    if ($backendService) {
        Write-Host "  Stopping $BackendServiceName..." -ForegroundColor Yellow
        & $NssmPath stop $BackendServiceName 2>$null
        Write-Host "  Removing $BackendServiceName..." -ForegroundColor Yellow
        & $NssmPath remove $BackendServiceName confirm 2>$null
        Write-Host "  Backend service removed" -ForegroundColor Green
    } else {
        Write-Host "  Backend service not found" -ForegroundColor Gray
    }

    Write-Host ""
    Write-Host "Services uninstalled successfully!" -ForegroundColor Green
}

function Start-Services {
    Write-Host ""
    Write-Host "Starting services..." -ForegroundColor Cyan

    Start-Service -Name $BackendServiceName -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 3
    Start-Service -Name $FrontendServiceName -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2

    Write-Host ""
    Write-Host "Service Status:" -ForegroundColor Cyan
    Get-Service -Name $BackendServiceName, $FrontendServiceName | Format-Table Name, Status, DisplayName -AutoSize
}

# Create logs directory
$logsDir = Join-Path $ProjectRoot "logs"
if (-not (Test-Path $logsDir)) {
    New-Item -ItemType Directory -Path $logsDir -Force | Out-Null
    Write-Host "Created logs directory: $logsDir" -ForegroundColor Gray
}

# Main execution
if ($Uninstall) {
    Get-NSSM
    Uninstall-Services
} else {
    Get-NSSM

    $backendOk = Install-BackendService
    $frontendOk = Install-FrontendService

    if ($backendOk -and $frontendOk) {
        Start-Services

        Write-Host ""
        Write-Host "========================================" -ForegroundColor Green
        Write-Host "  Installation Complete!" -ForegroundColor Green
        Write-Host "========================================" -ForegroundColor Green
        Write-Host ""
        Write-Host "The LLM Council services are now installed and running."
        Write-Host ""
        Write-Host "Access the application at:" -ForegroundColor Cyan
        Write-Host "  http://localhost:5173" -ForegroundColor White
        Write-Host ""
        Write-Host "Manage services with:" -ForegroundColor Cyan
        Write-Host "  services.msc           - Windows Services Manager" -ForegroundColor Gray
        Write-Host "  sc query LLMCouncil*   - Check service status" -ForegroundColor Gray
        Write-Host ""
        Write-Host "Log files are in:" -ForegroundColor Cyan
        Write-Host "  $logsDir" -ForegroundColor Gray
        Write-Host ""
        Write-Host "To uninstall, run:" -ForegroundColor Cyan
        Write-Host "  .\install-services.ps1 -Uninstall" -ForegroundColor Gray
    } else {
        Write-Host ""
        Write-Host "Installation failed. Check the errors above." -ForegroundColor Red
    }
}
