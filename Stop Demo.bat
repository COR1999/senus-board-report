@echo off
REM Double-click to stop the local demo (backend/frontend) and clear
REM local_demo.db. Optional -- "Start Demo.bat" does this automatically at
REM the start of every run too.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\local-demo\stop.ps1"
pause
