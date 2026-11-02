@echo off
chcp 65001 >nul
REM ⚠️ 推荐使用 sync-all.cmd（同步所有技能）
REM 本脚本仅同步 mercadolibre-listing-collector，不包含 latam 和 codex
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0sync-collector-skill.ps1"
echo.
pause