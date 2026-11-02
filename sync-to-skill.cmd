@echo off
chcp 65001 >nul
REM ⚠️ 推荐使用 sync-all.cmd（同步所有技能）
REM 本脚本仅同步 latam-tiktok-listing，不包含 codex-skill 和 collector
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0sync-to-skill.ps1"
echo.
pause
