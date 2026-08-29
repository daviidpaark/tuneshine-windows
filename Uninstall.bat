@echo off
cd /d "%~dp0"
echo Uninstalling Tuneshine Windows...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0uninstall.ps1"
pause
