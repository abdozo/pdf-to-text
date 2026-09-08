@echo off
setlocal
cd /d "%~dp0.."

where py >nul 2>nul
if errorlevel 1 (
  echo Python 3.11 or newer is required to stop a source checkout of Warraq.
  pause
  exit /b 1
)

py -3 scripts\manage_warraq.py stop
if errorlevel 1 (
  pause
  exit /b 1
)
