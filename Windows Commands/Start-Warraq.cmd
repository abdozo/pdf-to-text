@echo off
setlocal
cd /d "%~dp0.."

where py >nul 2>nul
if errorlevel 1 (
  echo Warraq requires Python 3.11 or newer. Install Python, then try again.
  pause
  exit /b 1
)

py -3 scripts\manage_warraq.py start
if errorlevel 1 (
  echo.
  echo Warraq did not start. The error and log path are shown above.
  pause
  exit /b 1
)
