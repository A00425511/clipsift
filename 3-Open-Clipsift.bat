@echo off
cd /d "%~dp0"

if not exist ".venv" (
  echo No virtual environment found. Run 1-Setup.bat first.
  pause
  exit /b 1
)

echo Starting ClipSift...
start "ClipSift server" /min .venv\Scripts\python.exe -m app.server --runs runs --port 8765
timeout /t 5 /nobreak >nul
start http://127.0.0.1:8765

echo ClipSift is open in your browser.
pause
