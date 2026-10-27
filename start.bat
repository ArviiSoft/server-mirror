@echo off
setlocal
set "PYTHONUTF8=1"
set "MIRROR_INTERACTIVE="
set "MIRROR_EXIT_CODE=0"
if "%~1"=="" set "MIRROR_INTERACTIVE=1"
title Server Mirror
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Create the virtual environment and install requirements/runtime.txt first. See README.md.
    set "MIRROR_EXIT_CODE=1"
    goto finish
)
if not defined MIRROR_INTERACTIVE goto run_arguments

echo.
echo Server Mirror
echo.
echo   1. Preview only - no server changes
echo   2. Copy - review and confirm the destination server ID before copying
echo   3. Exit
echo.
choice /c 123 /n /m "Select [1/2/3]: "
if errorlevel 4 goto selection_failed
if errorlevel 3 exit /b 0
if errorlevel 2 goto run_copy
if errorlevel 1 goto run_preview
set "MIRROR_EXIT_CODE=130"
goto finish

:selection_failed
echo Unable to read the mode selection. Run start.bat from an interactive terminal.
set "MIRROR_EXIT_CODE=1"
goto finish

:run_copy
".venv\Scripts\python.exe" -m server_mirror --apply
set "MIRROR_EXIT_CODE=%errorlevel%"
goto finish

:run_preview
".venv\Scripts\python.exe" -m server_mirror
set "MIRROR_EXIT_CODE=%errorlevel%"
goto finish

:run_arguments
".venv\Scripts\python.exe" -m server_mirror %*
set "MIRROR_EXIT_CODE=%errorlevel%"

:finish
if defined MIRROR_INTERACTIVE (
    echo.
    echo Press any key to close this window . . .
    pause >nul
)
exit /b %MIRROR_EXIT_CODE%
