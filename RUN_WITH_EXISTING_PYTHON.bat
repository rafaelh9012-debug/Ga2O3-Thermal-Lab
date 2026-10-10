@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
title Ga2O3 Thermal Lab - RafaelDaSquidman

echo ============================================================
echo   Ga2O3 Thermal Lab
echo   Publisher: RafaelDaSquidman
echo   Uses an existing Python installation - no Python download
echo ============================================================
echo.

set "PYEXE="
set "PYARG="

REM Try the official Python launcher first and verify that each candidate really runs.
where py >nul 2>nul
if !errorlevel! EQU 0 (
    for %%V in (3.14 3.13 3.12 3.11) do (
        if not defined PYEXE (
            py -%%V -c "import sys; raise SystemExit(0 if (3,11) <= sys.version_info[:2] < (3,15) else 1)" >nul 2>nul
            if !errorlevel! EQU 0 (
                set "PYEXE=py"
                set "PYARG=-%%V"
            )
        )
    )
)

REM Try normal PATH commands, while rejecting the Microsoft Store execution alias.
if not defined PYEXE (
    python -c "import sys; raise SystemExit(0 if (3,11) <= sys.version_info[:2] < (3,15) else 1)" >nul 2>nul
    if !errorlevel! EQU 0 set "PYEXE=python"
)
if not defined PYEXE (
    python3 -c "import sys; raise SystemExit(0 if (3,11) <= sys.version_info[:2] < (3,15) else 1)" >nul 2>nul
    if !errorlevel! EQU 0 set "PYEXE=python3"
)

REM Common Anaconda / Miniconda / python.org per-user locations.
if not defined PYEXE (
    for %%P in (
        "%USERPROFILE%\anaconda3\python.exe"
        "%USERPROFILE%\miniconda3\python.exe"
        "%LOCALAPPDATA%\anaconda3\python.exe"
        "%LOCALAPPDATA%\miniconda3\python.exe"
        "%LOCALAPPDATA%\Programs\Python\Python314\python.exe"
        "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
        "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
        "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    ) do (
        if not defined PYEXE if exist "%%~P" (
            "%%~P" -c "import sys; raise SystemExit(0 if (3,11) <= sys.version_info[:2] < (3,15) else 1)" >nul 2>nul
            if !errorlevel! EQU 0 set "PYEXE=%%~P"
        )
    )
)

if defined PYEXE goto :run

echo No compatible command-line Python 3.11-3.14 was found.
echo.
echo Nothing will be downloaded or installed automatically.
echo.
echo If you already use Spyder, Anaconda, VS Code, PyCharm, or IDLE:
echo   1. Open START_APP.py in that application.
echo   2. Press its normal Run button.
echo.
echo Opening the folder now so START_APP.py is easy to find.
start "" explorer.exe "%~dp0"
echo.
pause
exit /b 1

:run
echo Found existing Python: %PYEXE% %PYARG%
echo.
if "%PYEXE%"=="py" (
    py %PYARG% "%~dp0START_APP.py"
) else (
    "%PYEXE%" "%~dp0START_APP.py"
)
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (
    echo.
    echo Launcher ended with an error.
    pause
)
exit /b %RC%
