@echo off
rem Start Ollama Chat on Windows.
rem Creates .venv on first run, installs the package, then runs the server.
rem Any arguments are passed to ollama-chat (e.g. start.bat -p 8080).
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment in .venv ...
    python -m venv .venv
    if errorlevel 1 (
        echo Failed to create virtual environment. Make sure Python 3.11+ is installed and on PATH.
        exit /b 1
    )
)

call ".venv\Scripts\activate.bat"
rem Drop pip leftovers from interrupted installs (they cause "Ignoring invalid distribution" warnings)
for /d %%d in (".venv\Lib\site-packages\~*") do if exist "%%d" rd /s /q "%%d" 2>nul
python -m pip install --quiet --upgrade pip
if errorlevel 1 exit /b 1
python -m pip install --quiet -e .
if errorlevel 1 exit /b 1

ollama-chat %*
