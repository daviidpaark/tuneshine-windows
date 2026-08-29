@echo off
cd /d "%~dp0"
echo Starting Tuneshine Windows Installer...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0installer.ps1"
pause
