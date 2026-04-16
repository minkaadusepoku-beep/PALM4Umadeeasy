@echo off
REM One-click launcher for PALM4Umadeeasy (double-clickable).
REM Delegates to Start-PALM4Umadeeasy.ps1 next to this file.
REM
REM Pass arguments through, e.g.:
REM   Start-PALM4Umadeeasy.bat -Mode prod
REM   Start-PALM4Umadeeasy.bat -NoBrowser

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Start-PALM4Umadeeasy.ps1" %*
if errorlevel 1 (
    echo.
    echo PALM4Umadeeasy launcher reported an error.
    pause
)
