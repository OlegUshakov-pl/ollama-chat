@echo off
rem Install Ollama Chat on Windows.
rem Clones https://github.com/OlegUshakov-pl/ollama-chat into a clean folder (if needed),
rem creates .venv and installs dependencies.
rem Usage: put this file into an empty folder and double-click it, or run it inside an existing clone.
setlocal
cd /d "%~dp0"

rem If we are not inside a git clone, clone the repository
if not exist ".git" (
    if not exist "ollama-chat\.git" (
        echo Cloning https://github.com/OlegUshakov-pl/ollama-chat.git ...
        where git >nul 2>nul
        if errorlevel 1 (
            echo Git is not found. Please install Git from https://git-scm.com/download/win
            exit /b 1
        )
        git clone https://github.com/OlegUshakov-pl/ollama-chat.git
        if errorlevel 1 (
            echo Failed to clone repository.
            exit /b 1
        )
    )
    if exist "ollama-chat\install.bat" (
        cd /d "%~dp0ollama-chat"
    ) else (
        echo Clone completed but ollama-chat folder not found.
        exit /b 1
    )
)

echo Installing in: %CD%

if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment in .venv ...
    python -m venv .venv
    if errorlevel 1 (
        echo Failed to create virtual environment. Make sure Python 3.11+ is installed and on PATH.
        exit /b 1
    )
)

call ".venv\Scripts\activate.bat"
if errorlevel 1 (
    echo Failed to activate virtual environment.
    exit /b 1
)

rem Drop pip leftovers from interrupted installs (they cause "Ignoring invalid distribution" warnings)
for /d %%d in (".venv\Lib\site-packages\~*") do if exist "%%d" rd /s /q "%%d" 2>nul

echo Upgrading pip ...
python -m pip install --upgrade pip
if errorlevel 1 exit /b 1

echo Installing ollama-chat and dependencies ...
python -m pip install -e .
if errorlevel 1 exit /b 1

echo.
echo Installation complete.
echo   cd /d "%CD%"
echo   start.bat        - start on default port 8080
echo   start.bat -p 8080 - custom port
