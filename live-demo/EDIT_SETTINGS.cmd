@echo off
setlocal
cd /d "%~dp0"
set PYTHONUTF8=1
notepad config.json
if errorlevel 1 echo Error: read the messages above.
pause
