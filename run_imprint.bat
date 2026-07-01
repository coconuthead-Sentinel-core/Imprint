@echo off
REM Double-click launcher for Imprint. Opens the desktop app.
REM PYTHONUTF8 keeps all I/O in UTF-8 so Unicode (emoji, symbols) never trips the
REM Windows console codepage (the mojibake bug seen in the Turbo tool).
set PYTHONUTF8=1
cd /d "%~dp0"
py -3 imprint_app.py
if errorlevel 1 (
  echo.
  echo Imprint exited with an error. Press any key to close.
  pause >nul
)
