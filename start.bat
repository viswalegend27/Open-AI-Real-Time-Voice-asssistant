@echo off
REM --- Ishmael Voice Assistant - Clean Startup Script ---

echo [*] Checking Python ...
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed or not in PATH.
    pause
    exit /b 1
)

if not exist "venv\" (
    echo [*] Creating virtual environment...
    python -m venv venv
)

echo [*] Activating virtual environment ...
call venv\Scripts\activate.bat

echo [*] Installing dependencies ...
pip install -q -r requirements.txt

if not exist ".env" (
    echo ERROR: .env file not found!
    pause
    exit /b 1
)

REM Start Celery in the background, Django in the foreground
start "" cmd /c "call venv\Scripts\activate.bat && celery -A voice_assistant worker -l info --pool=solo"
echo [*] Celery started in a background window.

echo [*] Starting Django development server...
python manage.py runserver 127.0.0.1:8000

REM When Django server stops, kill celery (optional, advanced)
REM taskkill /FI "WINDOWTITLE eq Celery Worker" /F

echo [*] Shutdown complete.
pause