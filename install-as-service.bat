@echo off
:: LLM Council Service Installer
:: This script runs the PowerShell installer with admin privileges

echo ========================================
echo   LLM Council Service Installer
echo ========================================
echo.

:: Check if running as admin
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Requesting administrator privileges...
    powershell -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

:: Already admin, run the installer
cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -File "services\install-services.ps1"

echo.
pause
