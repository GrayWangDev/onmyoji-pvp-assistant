@echo off
cd /d "%~dp0"
python bp_live_monitor.py
if errorlevel 1 (
  echo.
  echo Failed to start. Please make sure Python is installed.
  pause
)
