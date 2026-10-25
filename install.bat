@echo off
rem Swarmbly AI - double-click installer for Windows.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" %*
echo.
pause
