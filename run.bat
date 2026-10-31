@echo off
setlocal
cd /d "%~dp0"

rem Starts the NetSleuth tray icon, which runs and watches the backend.
rem No administrator rights needed unless Npcap was installed admin-only.

if not exist ".venv\Scripts\pythonw.exe" (
    echo NetSleuth isn't set up yet. Run setup.bat first.
    pause
    exit /b 1
)
start "" ".venv\Scripts\pythonw.exe" "%~dp0tray\launch.pyw"
endlocal
