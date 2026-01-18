# stop-dev.ps1 - Clean shutdown of development environment

param(
    [switch]$All,           # Stop everything including SSH tunnel
    [switch]$BackendOnly,   # Only stop backend
    [switch]$FrontendOnly   # Only stop frontend
)

$ErrorActionPreference = "Continue"

Write-Host "`n=== Stopping Dejavara Dev Environment ===" -ForegroundColor Cyan
Write-Host ""

function Stop-PortProcess {
    param(
        [int]$Port,
        [string]$ServiceName
    )

    $connection = netstat -ano | Select-String ":$Port\s+.*LISTENING"
    if ($connection) {
        $procId = ($connection.Line.Trim() -split '\s+')[-1]

        try {
            $process = Get-Process -Id $procId -ErrorAction SilentlyContinue
            $processName = if ($process) { $process.ProcessName } else { "Unknown" }
        } catch {
            $processName = "Unknown"
        }

        Write-Host "Stopping $ServiceName on port $Port (PID: $procId, Process: $processName)..." -NoNewline

        taskkill /PID $procId /F 2>$null | Out-Null

        Start-Sleep -Milliseconds 500

        # Verify stopped
        $stillRunning = netstat -ano | Select-String ":$Port\s+.*LISTENING"
        if ($stillRunning) {
            Write-Host " [FAILED]" -ForegroundColor Red
            return $false
        } else {
            Write-Host " [OK]" -ForegroundColor Green
            return $true
        }
    } else {
        Write-Host "$ServiceName (port $Port) - not running" -ForegroundColor DarkGray
        return $true
    }
}

$stopped = @()
$failed = @()

# Stop frontend
if (-not $BackendOnly) {
    # Try both possible frontend ports
    foreach ($port in @(5173, 5174)) {
        $connection = netstat -ano | Select-String ":$port\s+.*LISTENING"
        if ($connection) {
            if (Stop-PortProcess -Port $port -ServiceName "LLM Council Frontend") {
                $stopped += "Frontend ($port)"
            } else {
                $failed += "Frontend ($port)"
            }
        }
    }
}

# Stop backend
if (-not $FrontendOnly) {
    if (Stop-PortProcess -Port 8001 -ServiceName "LLM Council Backend") {
        $stopped += "Backend (8001)"
    } else {
        $failed += "Backend (8001)"
    }
}

# Stop SSH tunnel if -All specified
if ($All) {
    if (Stop-PortProcess -Port 5433 -ServiceName "PostgreSQL SSH Tunnel") {
        $stopped += "SSH Tunnel (5433)"
    } else {
        $failed += "SSH Tunnel (5433)"
    }
}

Write-Host ""
Write-Host "=== Summary ===" -ForegroundColor Cyan

if ($stopped.Count -gt 0) {
    Write-Host "Stopped: $($stopped -join ', ')" -ForegroundColor Green
}

if ($failed.Count -gt 0) {
    Write-Host "Failed: $($failed -join ', ')" -ForegroundColor Red
}

if ($stopped.Count -eq 0 -and $failed.Count -eq 0) {
    Write-Host "No services were running." -ForegroundColor Yellow
}

Write-Host ""
