@echo off
setlocal
cd /d "%~dp0"
set PYTHONUTF8=1
set "PY="
if exist "runtime\python.exe" set "PY=runtime\python.exe"
if not defined PY if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"
if not defined PY (
  echo Please run SETUP_WINDOWS.cmd first.
  pause
  exit /b 1
)
"%PY%" wearable_bridge.py
if errorlevel 1 echo Error: read the messages above.
pause
