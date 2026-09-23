@echo off
cd /d "%~dp0"
for %%I in ("%CD%") do set "AppName=%%~nxI"
if exist ".venv\Scripts\pythonw.exe" (
  start "" ".venv\Scripts\pythonw.exe" -m mahjong_assistant
  exit /b
)
if exist "dist\%AppName%-v0.3\%AppName%-v0.3.exe" (
  start "" "dist\%AppName%-v0.3\%AppName%-v0.3.exe"
  exit /b
)
if exist "dist\%AppName%-v0.2\%AppName%-v0.2.exe" (
  start "" "dist\%AppName%-v0.2\%AppName%-v0.2.exe"
  exit /b
)
if exist "dist\%AppName%\%AppName%.exe" (
  start "" "dist\%AppName%\%AppName%.exe"
  exit /b
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start.ps1"
if errorlevel 1 pause
