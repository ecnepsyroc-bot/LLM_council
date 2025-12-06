# Start script for LLM Council on Windows

Write-Host "Starting LLM Council..."
Write-Host ""

# Start backend
Write-Host "Starting backend on http://localhost:8001..."
$backendProcess = Start-Process -FilePath "python" -ArgumentList "-m", "backend.main" -PassThru -NoNewWindow
Start-Sleep -Seconds 2

# Start frontend
Write-Host "Starting frontend on http://localhost:5173..."
Set-Location frontend
$frontendProcess = Start-Process -FilePath "npm" -ArgumentList "run", "dev" -PassThru -NoNewWindow
Set-Location ..

Write-Host ""
Write-Host "✓ LLM Council is running!"
Write-Host "  Backend:  http://localhost:8001"
Write-Host "  Frontend: http://localhost:5173"
Write-Host ""
Write-Host "Press Ctrl+C to stop both servers"

try {
    # Wait indefinitely
    while ($true) {
        Start-Sleep -Seconds 1
        if ($backendProcess.HasExited -or $frontendProcess.HasExited) {
            break
        }
    }
}
finally {
    Write-Host "Stopping servers..."
    Stop-Process -Id $backendProcess.Id -ErrorAction SilentlyContinue
    Stop-Process -Id $frontendProcess.Id -ErrorAction SilentlyContinue
}
