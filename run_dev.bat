@echo off
echo Starting Warehouse Transfer Planning Tool - Development Mode...
echo.

REM Set environment variables for development
set DEBUG=true
set ENVIRONMENT=development

echo [1/4] Killing any existing processes on port 8000...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000') do (
    echo Terminating process %%a
    taskkill /F /PID %%a >nul 2>&1
)

echo [2/4] Clearing Python cache...
if exist backend\__pycache__ (
    rmdir /s /q backend\__pycache__
    echo Python cache cleared
)

echo [3/4] Activating virtual environment...
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
    echo Virtual environment activated
) else (
    echo Warning: Virtual environment not found, using system Python
)

echo [4/4] Starting FastAPI server with hot reload...
echo.
echo Server will start on: http://localhost:8000
echo Press Ctrl+C to stop the server
echo.

cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000 --reload-include "*.py" --reload-include "*.html" --reload-include "*.css" --reload-include "*.js" --log-level info

pause