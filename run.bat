@echo off
cd /d "%~dp0"
echo Starting Tuneshine Windows Desktop Companion...
call .\.venv\Scripts\python.exe main.py
pause
