@echo off
setlocal
cd /d "%~dp0"
if exist "runtime\python.exe" (
  echo Portable runtime is already included. No setup is needed.
  pause
  exit /b 0
)
where py >nul 2>nul || (echo Python 3.11 x64 is required. & pause & exit /b 1)
if not exist ".venv\Scripts\python.exe" py -3.11 -m venv .venv
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements-runtime.txt
if errorlevel 1 (
  echo Setup failed. Check the messages above.
  pause
  exit /b 1
)
echo MindLink setup complete.
pause
