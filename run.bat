@echo off
setlocal

:: Packet capture requires admin
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo  [!] NetSleuth requires Administrator privileges for packet capture.
    echo      Right-click this file and select "Run as administrator".
    echo.
    pause
    exit /b 1
)

set ROOT=%~dp0

:: Install frontend deps if needed
if not exist "%ROOT%frontend\node_modules" (
    echo  [i] Installing frontend dependencies...
    pushd "%ROOT%frontend"
    npm install
    popd
    echo.
    echo  [i] Dependencies installed. Re-run this script to start NetSleuth.
    echo.
    pause
    exit /b 0
)

python "%ROOT%launcher.py"

endlocal
