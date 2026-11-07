@echo off
rem Double-click to start ClipSift. It runs on this computer only. Close this window to stop it.
cd /d "%~dp0"
set PY=python
if exist .venv\Scripts\python.exe set PY=.venv\Scripts\python.exe
"%PY%" -m app.server --open
if errorlevel 1 pause
