@echo off
rem TickerQuill for Windows: double-click this file to start the app.
rem The first time, it also installs TickerQuill into .venv and makes a Start Menu + Desktop shortcut.
rem Needs Python 3.10 or newer (https://www.python.org/downloads/, with "tcl/tk and IDLE"), or uv.
cd /d "%~dp0"

if exist ".venv\Scripts\pythonw.exe" if exist ".venv\Scripts\tickerquill-gui.exe" goto run

title TickerQuill setup
echo Setting up TickerQuill for the first time.
echo This downloads the dependencies and can take a few minutes. Keep this window open.
echo.
rem A Python that really runs and is 3.10+ (the Microsoft Store "python" placeholder does not count).
set "PY="
py -3 -c "import sys; sys.exit(sys.version_info < (3, 10))" >nul 2>nul && set "PY=py -3"
if not defined PY python -c "import sys; sys.exit(sys.version_info < (3, 10))" >nul 2>nul && set "PY=python"
if defined PY goto venv
where uv >nul 2>nul && goto uv
goto nopython

:venv
%PY% -m venv .venv || goto failed
".venv\Scripts\python.exe" -m pip install --upgrade pip || goto failed
".venv\Scripts\python.exe" -m pip install -r requirements.txt || goto failed
goto shortcut

:uv
echo No Python 3.10+ found; using uv to set one up.
uv venv --python ">=3.10" .venv || goto failed
uv pip install --python ".venv\Scripts\python.exe" -r requirements.txt || goto failed

:shortcut
".venv\Scripts\python.exe" -m tickerquill --shortcut
echo.
echo Done. Next time you can also start TickerQuill from the Start Menu or the Desktop shortcut.
echo.

:run
rem pythonw: no console window. Problems? Run ".venv\Scripts\tickerquill.exe" in a terminal to see the messages.
start "" ".venv\Scripts\pythonw.exe" -m tickerquill
exit /b 0

:nopython
echo Python 3.10 or newer was not found.
echo Install it from https://www.python.org/downloads/ (tick "Add python.exe to PATH"),
echo then double-click TickerQuill.bat again.
pause
exit /b 1

:failed
echo.
echo Setting up failed; the messages above say why (often no internet connection).
echo Fix it, then double-click TickerQuill.bat again. To start over, delete the .venv folder first.
pause
exit /b 1
