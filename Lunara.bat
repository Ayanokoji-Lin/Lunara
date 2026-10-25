@echo off
rem ===================================================================
rem  Lunara launcher
rem    Lunara.bat            - start without a console window
rem    Lunara.bat -c         - start with console (see logs live)
rem ===================================================================
setlocal
cd /d "%~dp0"

set "PYW=%CD%\.venv\Scripts\pythonw.exe"
set "PY=%CD%\.venv\Scripts\python.exe"

if /i "%~1"=="-c" goto console
if /i "%~1"=="--console" goto console
goto silent

:silent
if exist "%PYW%" (
    start "" "%PYW%" "%CD%\main.py"
    exit /b 0
)
if exist "%PY%" (
    start "" "%PY%" "%CD%\main.py"
    exit /b 0
)
goto nopython

:console
if exist "%PY%" (
    "%PY%" "%CD%\main.py"
    exit /b %errorlevel%
)
goto nopython

:nopython
echo.
echo  [Lunara] Python environment not found.
echo.
echo  Expected: %CD%\.venv\Scripts\python.exe
echo  Create it with:
echo      python -m venv .venv
echo      .venv\Scripts\python.exe -m pip install -r requirements.txt
echo.
pause
exit /b 1
