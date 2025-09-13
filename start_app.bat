@echo off
echo Starting Warehouse Transfer Planning Tool...

REM Start the frontend server
echo Starting frontend server on port 8090...
cd frontend
start /min python -m http.server 8090
cd ..

REM Wait a moment for server to start
timeout /t 5 /nobreak >nul

REM Open the frontend in default browser
echo Opening frontend...
start http://localhost:8090

echo.
echo Application started!
echo Backend: http://localhost:8002 (already running)
echo Frontend: http://localhost:8090
echo.
pause