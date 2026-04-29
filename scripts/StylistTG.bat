@echo off
setlocal
title StylistTG Dev

set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%.."

cd /d "%PROJECT_ROOT%" || (
    echo.
    echo   ERROR: Failed to enter project directory.
    echo.
    pause
    exit /b 1
)

powershell.exe -ExecutionPolicy Bypass -NoProfile -File "%SCRIPT_DIR%start-dev.ps1" %*
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
    echo.
    echo   ERROR: Script exited with code %EXIT_CODE%.
    echo.
    pause
)

exit /b %EXIT_CODE%
