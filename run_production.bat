@echo off
echo Starting Warehouse Transfer Planning Tool - Production Mode...
echo.

REM Set environment variables for production
set DEBUG=false
set ENVIRONMENT=production

echo [1/4] Killing any existing development processes...
call kill_server.bat

echo [2/4] Activating virtual environment...
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
    echo Virtual environment activated
) else (
    echo Warning: Virtual environment not found, using system Python
)

echo [3/4] Starting FastAPI server in production mode...
echo.
echo Server will start on: http://localhost:8000
echo Production mode: Static file caching ENABLED
echo Press Ctrl+C to stop the server
echo.

cd backend
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4 --log-level warning

pause