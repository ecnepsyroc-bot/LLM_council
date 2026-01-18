# check-ports.ps1 - Verify port state matches registry

$ErrorActionPreference = "Continue"

# Port registry
$ports = @(
    @{ Port = 5173; Service = "LLM Council Frontend"; Required = $false }
    @{ Port = 5174; Service = "LLM Council Frontend (alt)"; Required = $false }
    @{ Port = 5433; Service = "PostgreSQL SSH Tunnel"; Required = $false }
    @{ Port = 8001; Service = "LLM Council Backend"; Required = $false }
)

Write-Host "`n=== Dejavara Port Registry Check ===" -ForegroundColor Cyan
Write-Host ""

$results = @()

foreach ($entry in $ports) {
    $port = $entry.Port
    $service = $entry.Service

    # Check if port is listening
    $connection = netstat -ano | Select-String ":$port\s+.*LISTENING"

    if ($connection) {
        # Extract PID
        $line = $connection.Line.Trim()
        $procId = ($line -split '\s+')[-1]

        # Get process name
        try {
            $process = Get-Process -Id $procId -ErrorAction SilentlyContinue
            $processName = if ($process) { $process.ProcessName } else { "Unknown" }
        } catch {
            $processName = "Unknown"
        }

        Write-Host "[ACTIVE] " -ForegroundColor Green -NoNewline
        Write-Host "Port $port - $service" -NoNewline
        Write-Host " (PID: $procId, Process: $processName)" -ForegroundColor DarkGray

        $results += @{ Port = $port; Status = "Active"; PID = $procId; Process = $processName }
    } else {
        Write-Host "[IDLE]   " -ForegroundColor Yellow -NoNewline
        Write-Host "Port $port - $service"

        $results += @{ Port = $port; Status = "Idle"; PID = $null; Process = $null }
    }
}

Write-Host ""

# Check for unexpected listeners on reserved ranges
Write-Host "=== Checking for conflicts ===" -ForegroundColor Cyan
$reservedRanges = @(
    @{ Start = 5170; End = 5199; Name = "Frontend Dev" }
    @{ Start = 8000; End = 8099; Name = "Backend Services" }
)

$conflicts = @()
$allListening = netstat -ano | Select-String "LISTENING"

foreach ($range in $reservedRanges) {
    foreach ($line in $allListening) {
        if ($line -match ":(\d+)\s+") {
            $foundPort = [int]$matches[1]
            if ($foundPort -ge $range.Start -and $foundPort -le $range.End) {
                # Check if it's a known port
                $known = $ports | Where-Object { $_.Port -eq $foundPort }
                if (-not $known) {
                    $procId = ($line.Line.Trim() -split '\s+')[-1]
                    Write-Host "[CONFLICT] " -ForegroundColor Red -NoNewline
                    Write-Host "Unknown service on port $foundPort (PID: $procId) in $($range.Name) range"
                    $conflicts += $foundPort
                }
            }
        }
    }
}

if ($conflicts.Count -eq 0) {
    Write-Host "No conflicts detected." -ForegroundColor Green
}

Write-Host ""

# Summary
$active = ($results | Where-Object { $_.Status -eq "Active" }).Count
$idle = ($results | Where-Object { $_.Status -eq "Idle" }).Count

Write-Host "=== Summary ===" -ForegroundColor Cyan
Write-Host "Active: $active | Idle: $idle | Conflicts: $($conflicts.Count)"
Write-Host ""
