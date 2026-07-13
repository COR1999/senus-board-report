@echo off
REM Double-click this file to start the fully local, isolated Presentation
REM Mode demo -- fresh local SQLite DB, local backend, local frontend.
REM Never touches backend\.env, frontend\.env.local, or production.
REM See scripts\local-demo\run.ps1 for what this actually does.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\local-demo\run.ps1"
pause
