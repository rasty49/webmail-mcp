@echo off
setlocal
cd /d "%~dp0"
py -3 -c "import sys; assert sys.version_info >= (3,11)" >nul 2>&1
if errorlevel 1 (
  echo Install Python 3.11 or newer with its launcher and Tcl/Tk support, then try again.
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" py -3 -m venv .venv
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -I -m pip install --require-hashes --only-binary=:all: -r requirements.lock
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -I -m pip install --no-build-isolation --no-deps .
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -I -m webmail_mcp setup
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -I -m webmail_mcp check
if errorlevel 1 goto failed
echo.
echo Launch settings for your MCP client:
".venv\Scripts\python.exe" -I -m webmail_mcp client-config
echo.
echo See README.md to connect ChatGPT desktop or Claude Code.
pause
exit /b 0
:failed
echo Setup or connection check failed. No email was sent. See README.md.
pause
exit /b 1
