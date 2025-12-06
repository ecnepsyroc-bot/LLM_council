@echo off
:: LLM Council - Windows Launcher
:: Double-click this file to start LLM Council with a system tray icon
:: You can pin this to Start menu or taskbar

cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -WindowStyle Hidden -File "LLMCouncil-Tray.ps1"
