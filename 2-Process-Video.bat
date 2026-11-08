@echo off
cd /d "%~dp0"

if "%~1"=="" (
  echo Drag a video file onto this script.
  echo Example: drag T1-STAT2 411.MP4 onto 2-Process-Video.bat
  pause
  exit /b 1
)

if not exist ".venv" (
  echo No virtual environment found. Run 1-Setup.bat first.
  pause
  exit /b 1
)

echo Processing %~1 ...
.venv\Scripts\python.exe -m clipsift run "%~1" --config config\yolo.yaml --out runs

echo.
echo Done. Next: run 3-Open-ClipSift.bat to review the results.
pause
