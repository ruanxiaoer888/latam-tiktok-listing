@echo off
chcp 65001 >nul
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup-new-pc.ps1" -FullCheck
echo.
pause
