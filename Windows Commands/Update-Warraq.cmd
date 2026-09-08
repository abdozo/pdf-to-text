@echo off
setlocal
cd /d "%~dp0.."

call "%~dp0Stop-Warraq.cmd"
if errorlevel 1 exit /b 1

git checkout main
if errorlevel 1 goto :update_failed

git pull
if errorlevel 1 goto :update_failed

call "%~dp0Start-Warraq.cmd"
exit /b %errorlevel%

:update_failed
echo.
echo Warraq could not be updated. It remains stopped so the Git error can be fixed safely.
pause
exit /b 1
