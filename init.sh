#!/bin/bash
# Purpose: Start the development environment from scratch
# Usage: ./init.sh (Linux/Mac) or use init.ps1 on Windows

set -e

echo "=== LLM Council Environment Setup ==="
echo ""

# Check for required tools
echo "Checking prerequisites..."
command -v python >/dev/null 2>&1 || { echo "ERROR: Python is required but not installed."; exit 1; }
command -v node >/dev/null 2>&1 || { echo "ERROR: Node.js is required but not installed."; exit 1; }
command -v npm >/dev/null 2>&1 || { echo "ERROR: npm is required but not installed."; exit 1; }
echo "  Python: $(python --version)"
echo "  Node: $(node --version)"
echo "  npm: $(npm --version)"

# Check for .env file
if [ ! -f ".env" ]; then
    echo ""
    echo "WARNING: .env file not found. Copy .env.example and add your OPENROUTER_API_KEY"
fi

# Install backend dependencies
echo ""
echo "Installing backend dependencies..."
pip install -q fastapi uvicorn httpx python-dotenv

# Install frontend dependencies
echo ""
echo "Installing frontend dependencies..."
cd frontend
npm install --silent
cd ..

# Basic smoke test - check imports work
echo ""
echo "Running smoke test..."
python -c "from backend.config import COUNCIL_MODELS; print(f'  Council configured with {len(COUNCIL_MODELS)} models')"

echo ""
echo "=== Environment ready ==="
echo ""
echo "To start the servers:"
echo "  Backend:  python -m backend.main"
echo "  Frontend: npm run dev --prefix frontend"
echo ""
echo "Or use: ./start.ps1 (Windows) to run both"
