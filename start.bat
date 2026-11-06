@echo off
rem ============================================================
rem  CodeTutor AI launcher (double-click this file)
rem  Installs dependencies once, then starts both servers.
rem ============================================================
powershell -ExecutionPolicy Bypass -NoProfile -File "%~dp0start.ps1" %*
pause
