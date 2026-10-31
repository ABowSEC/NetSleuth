@echo off
setlocal
cd /d "%~dp0"

rem One-time setup. Run from a normal (non-administrator) terminal.
rem Creates .venv, installs the backend and tray, and builds the dashboard.

python -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
if errorlevel 1 (
    echo NetSleuth needs Python 3.11 or newer on your PATH: https://www.python.org/downloads/
    exit /b 1
)
where npm >nul 2>&1
if errorlevel 1 (
    echo NetSleuth needs Node.js 20.9 or newer to build the dashboard: https://nodejs.org/
    exit /b 1
)
if not exist "%SystemRoot%\System32\Npcap\wpcap.dll" (
    echo Note: Npcap isn't installed yet. NetSleuth needs it to see devices: https://npcap.com
    echo.
)

if not exist ".venv\Scripts\python.exe" (
    echo Creating Python environment in .venv ...
    python -m venv .venv
    if errorlevel 1 exit /b 1
)

echo Installing NetSleuth ...
".venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
".venv\Scripts\python.exe" -m pip install --quiet -e backend -r tray\requirements.txt
if errorlevel 1 exit /b 1

echo Building the dashboard ...
pushd frontend
call npm ci --no-audit --no-fund
if errorlevel 1 (popd & exit /b 1)
call npm run build
if errorlevel 1 (popd & exit /b 1)
popd

echo.
echo Setup complete. Start NetSleuth with run.bat.
endlocal
