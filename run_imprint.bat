@echo off
REM Double-click launcher for Imprint. Opens the desktop app.
cd /d "%~dp0"
py -3 imprint_app.py
if errorlevel 1 (
  echo.
  echo Imprint exited with an error. Press any key to close.
  pause >nul
)
