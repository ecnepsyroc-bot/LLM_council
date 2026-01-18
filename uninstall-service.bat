@echo off
:: LLM Council Service Uninstaller
:: This script removes the Windows services

echo ========================================
echo   LLM Council Service Uninstaller
echo ========================================
echo.

:: Check if running as admin
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Requesting administrator privileges...
    powershell -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

:: Already admin, run the uninstaller
cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -File "services\install-services.ps1" -Uninstall

echo.
pause
