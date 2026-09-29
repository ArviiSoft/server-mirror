@echo off
setlocal
set PYTHONUTF8=1
title Server Mirror
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Create the virtual environment and install requirements/runtime.txt first. See README.md.
    exit /b 1
)
".venv\Scripts\python.exe" -m server_mirror %*
exit /b %errorlevel%