@echo off
rem Swarmbly App - one-command launcher (Windows).
rem   launch.bat            check, prepare (asks first) and start
rem   launch.bat --check    report only
rem   launch.bat --help     all options
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
  if not errorlevel 1 (
    py -3 scripts\launch.py %*
    goto :end
  )
)
where python >nul 2>nul
if %errorlevel%==0 (
  python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
  if not errorlevel 1 (
    python scripts\launch.py %*
    goto :end
  )
)
echo Swarmbly App needs Python 3.10 or newer: https://www.python.org/downloads/ (tick "Add to PATH").
pause
exit /b 1
:end
if errorlevel 1 pause
