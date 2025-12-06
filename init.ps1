# Purpose: Start the development environment from scratch (Windows)
# Usage: .\init.ps1

$ErrorActionPreference = "Stop"

Write-Host "=== LLM Council Environment Setup ===" -ForegroundColor Cyan
Write-Host ""

# Check for required tools
Write-Host "Checking prerequisites..."
try {
    $pythonVersion = python --version 2>&1
    Write-Host "  Python: $pythonVersion"
} catch {
    Write-Host "ERROR: Python is required but not installed." -ForegroundColor Red
    exit 1
}

try {
    $nodeVersion = node --version 2>&1
    Write-Host "  Node: $nodeVersion"
} catch {
    Write-Host "ERROR: Node.js is required but not installed." -ForegroundColor Red
    exit 1
}

try {
    $npmVersion = npm --version 2>&1
    Write-Host "  npm: $npmVersion"
} catch {
    Write-Host "ERROR: npm is required but not installed." -ForegroundColor Red
    exit 1
}

# Check for .env file
if (-not (Test-Path ".env")) {
    Write-Host ""
    Write-Host "WARNING: .env file not found. Copy .env.example and add your OPENROUTER_API_KEY" -ForegroundColor Yellow
}

# Install backend dependencies
Write-Host ""
Write-Host "Installing backend dependencies..."
pip install -q fastapi uvicorn httpx python-dotenv

# Install frontend dependencies
Write-Host ""
Write-Host "Installing frontend dependencies..."
Set-Location frontend
npm install --silent
Set-Location ..

# Basic smoke test - check imports work
Write-Host ""
Write-Host "Running smoke test..."
$smokeTest = python -c "from backend.config import COUNCIL_MODELS; print(f'  Council configured with {len(COUNCIL_MODELS)} models')"
Write-Host $smokeTest

Write-Host ""
Write-Host "=== Environment ready ===" -ForegroundColor Green
Write-Host ""
Write-Host "To start the servers:"
Write-Host "  Backend:  python -m backend.main"
Write-Host "  Frontend: npm run dev --prefix frontend"
Write-Host ""
Write-Host "Or use: .\start.ps1 to run both"
