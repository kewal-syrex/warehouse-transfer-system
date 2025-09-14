@echo off
setlocal enabledelayedexpansion
echo Terminating FastAPI server processes...
echo.

REM Method 1: Kill processes on port 8000 using PowerShell (more reliable)
echo [1/4] Using PowerShell to kill processes on port 8000...
powershell -Command "try { Get-NetTCPConnection -LocalPort 8000 -ErrorAction Stop | ForEach-Object { $pid = $_.OwningProcess; Write-Host \"Killing process $pid on port 8000\"; Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue } } catch { Write-Host \"No processes found on port 8000\" }" 2>nul

REM Method 2: Kill processes by command line pattern
echo [2/4] Killing Python processes running main.py or uvicorn...
for /f "tokens=2 delims=," %%i in ('wmic process where "CommandLine like '%%main:app%%' or CommandLine like '%%uvicorn%%'" get ProcessId /format:csv 2^>nul ^| findstr /r "[0-9]"') do (
    echo Terminating Python server process %%i
    taskkill /F /PID %%i >nul 2>&1
)

REM Method 3: Brute force - kill all python.exe in current directory tree
echo [3/4] Checking for Python processes in project directory...
for /f "tokens=2" %%i in ('wmic process where "name='python.exe' and CommandLine like '%%warehouse-transfer%%'" get ProcessId /format:value 2^>nul ^| find "ProcessId"') do (
    echo Killing project Python process %%i
    taskkill /F /PID %%i >nul 2>&1
)

REM Method 4: Clear any phantom network connections (Windows specific fix)
echo [4/4] Clearing network connection table...
netsh int ip reset >nul 2>&1

REM Wait a moment for cleanup
timeout /t 2 /nobreak >nul

REM Verify cleanup
echo.
echo Verification:
netstat -ano | findstr :8000 >nul
if %errorlevel% equ 0 (
    echo WARNING: Port 8000 still shows as in use - may be phantom connection
    echo Try restarting Windows if this persists
) else (
    echo SUCCESS: Port 8000 is now free
)

echo.
echo Server cleanup completed!
echo You can now run run_dev.bat to start a fresh server instance.
pause