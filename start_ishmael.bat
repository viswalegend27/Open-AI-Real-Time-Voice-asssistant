@echo off
REM ==========================================
REM Ishmael Voice Assistant - Startup Script
REM "Call me Ishmael..."
REM ==========================================

echo.
echo ========================================
echo    Starting Ishmael Voice Assistant
echo    "Call me Ishmael..."
echo ========================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    pause
    exit /b 1
)

REM Check if virtual environment exists
if not exist "venv\" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Install/update dependencies
echo Installing dependencies...
pip install -q fastapi uvicorn python-dotenv httpx

REM Check if .env file exists
if not exist ".env" (
    echo.
    echo WARNING: .env file not found!
    echo Please create a .env file with your OPENAI_API_KEY
    echo.
    pause
    exit /b 1
)

REM Start the server
echo.
echo ========================================
echo    Launching Ishmael Server...
echo ========================================
echo.

python server_realtime.py

REM Keep window open if there's an error
if errorlevel 1 (
    echo.
    echo ========================================
    echo    Server encountered an error
    echo ========================================
    pause
)
