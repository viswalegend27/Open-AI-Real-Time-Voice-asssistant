@echo off
REM ==========================================
REM Ishmael Voice Assistant - Startup Script
REM "Call me Ishmael..." - Django with Celery
REM ==========================================

echo.
echo ========================================
echo    Starting Ishmael Voice Assistant
echo    "Call me Ishmael..." (Django + Celery)
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
pip install -q -r requirements.txt

REM Check if .env file exists
if not exist ".env" (
    echo.
    echo WARNING: .env file not found!
    echo Please create a .env file with your OPENAI_API_KEY
    echo.
    pause
    exit /b 1
)

REM Start the Celery worker in a new command window
start "Celery Worker" cmd /k "call venv\Scripts\activate.bat && celery -A voice_assistant worker -l info --pool=solo"

REM Start the Django server in a new command window
start "Django Server" cmd /k "call venv\Scripts\activate.bat && python manage.py runserver 127.0.0.1:8000"

echo.
echo ========================================
echo Both servers started in new windows.
echo (Close this window if you don't need logs.)
echo ========================================
pause
