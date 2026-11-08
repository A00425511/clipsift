@echo off
cd /d "%~dp0"

echo Checking Python...
py --version >nul 2>&1
if errorlevel 1 (
  echo Python not found. Install Python 3.11 or newer from python.org
  echo and tick "Add Python to PATH" during install, then run this again.
  pause
  exit /b 1
)

echo Checking ffmpeg...
where ffmpeg >nul 2>&1
if errorlevel 1 (
  echo ffmpeg not found. Installing with winget...
  winget install -e --id Gyan.FFmpeg
  echo Close this window, open a new one, and run 1-Setup.bat again.
  pause
  exit /b 1
)

if not exist "models\clipsift-yolov8n.onnx" (
  echo Missing models\clipsift-yolov8n.onnx - the model file is not in this folder.
  pause
  exit /b 1
)

if not exist ".venv" (
  echo Creating virtual environment...
  py -m venv .venv
)

echo Installing requirements...
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt

echo.
echo Setup done. Next: drag a video onto 2-Process-Video.bat
pause
