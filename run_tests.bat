@echo off
rem Run the backend test suite (87 tests).
rem Creates the virtualenv and installs dev dependencies on first run.
powershell -ExecutionPolicy Bypass -NoProfile -File "%~dp0start.ps1" -RunTests
pause
