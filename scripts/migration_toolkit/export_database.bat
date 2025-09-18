@echo off
REM ===================================================================
REM Warehouse Transfer System - Database Export Script
REM Version: 1.0
REM Purpose: Export complete development database with all data
REM Usage: Run this script when ready to migrate to production
REM ===================================================================

echo.
echo ===============================================
echo Warehouse Transfer Database Export Tool
echo ===============================================
echo.

REM Get current date and time for unique filename
for /f "tokens=2 delims==" %%a in ('wmic OS Get localdatetime /value') do set "dt=%%a"
set "YY=%dt:~2,2%"
set "YYYY=%dt:~0,4%"
set "MM=%dt:~4,2%"
set "DD=%dt:~6,2%"
set "HH=%dt:~8,2%"
set "Min=%dt:~10,2%"
set "Sec=%dt:~12,2%"

set "datestamp=%YYYY%%MM%%DD%_%HH%%Min%%Sec%"
set "backup_file=warehouse_db_%datestamp%.sql"
set "zip_file=warehouse_db_%datestamp%.zip"

echo Backup will be saved as: %backup_file%
echo Compressed file will be: %zip_file%
echo.

REM Check if mysqldump is available
where mysqldump >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: mysqldump not found in PATH
    echo.
    echo Please check if MySQL is installed and mysqldump is in your PATH.
    echo Common MySQL installation paths:
    echo   - C:\Program Files\MySQL\MySQL Server 8.0\bin\
    echo   - C:\xampp\mysql\bin\
    echo.
    echo You can either:
    echo 1. Add MySQL bin directory to your PATH environment variable
    echo 2. Or edit this script to use the full path to mysqldump
    echo.
    pause
    exit /b 1
)

echo Step 1: Exporting database structure and data...
echo This may take a few minutes depending on your data size...
echo.

REM Export complete database with structure and data
mysqldump -u root -p ^
    --single-transaction ^
    --routines ^
    --triggers ^
    --events ^
    --add-drop-table ^
    --add-locks ^
    --extended-insert ^
    --quick ^
    --lock-tables=false ^
    warehouse_transfer > "%backup_file%"

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: Database export failed!
    echo.
    echo Common issues:
    echo 1. Incorrect MySQL password
    echo 2. Database 'warehouse_transfer' doesn't exist
    echo 3. MySQL server not running
    echo 4. Insufficient permissions
    echo.
    echo Please check your MySQL connection and try again.
    pause
    exit /b 1
)

echo ✓ Database exported successfully!
echo.

REM Check if the export file was created and has content
if not exist "%backup_file%" (
    echo ERROR: Export file was not created!
    pause
    exit /b 1
)

REM Check if file has reasonable size (should be at least 10KB for basic structure)
for %%F in ("%backup_file%") do set size=%%~zF
if %size% LSS 10240 (
    echo WARNING: Export file seems very small (%size% bytes)
    echo This might indicate an incomplete export.
    echo Please check the file contents before proceeding.
    echo.
)

echo Step 2: Compressing backup file...
echo.

REM Check if 7-zip is available (common compression tool)
where 7z >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    echo Using 7-Zip for compression...
    7z a "%zip_file%" "%backup_file%" >nul
    if %ERRORLEVEL% EQU 0 (
        echo ✓ File compressed with 7-Zip
        del "%backup_file%"
        echo ✓ Original SQL file removed (kept compressed version)
        goto :compression_done
    )
)

REM Check if WinRAR is available
where winrar >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    echo Using WinRAR for compression...
    winrar a "%zip_file%" "%backup_file%" >nul
    if %ERRORLEVEL% EQU 0 (
        echo ✓ File compressed with WinRAR
        del "%backup_file%"
        echo ✓ Original SQL file removed (kept compressed version)
        goto :compression_done
    )
)

REM Check if PowerShell is available for ZIP compression
powershell -command "Get-Command Compress-Archive" >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    echo Using PowerShell for compression...
    powershell -command "Compress-Archive -Path '%backup_file%' -DestinationPath '%zip_file%.zip' -Force"
    if %ERRORLEVEL% EQU 0 (
        echo ✓ File compressed with PowerShell
        del "%backup_file%"
        echo ✓ Original SQL file removed (kept compressed version)
        set "zip_file=%zip_file%.zip"
        goto :compression_done
    )
)

REM If no compression tool found, keep the SQL file
echo WARNING: No compression tool found (7-Zip, WinRAR, or PowerShell)
echo Keeping uncompressed SQL file: %backup_file%
set "zip_file=%backup_file%"

:compression_done

echo.
echo ===============================================
echo EXPORT COMPLETED SUCCESSFULLY!
echo ===============================================
echo.
echo Export Details:
echo   Database: warehouse_transfer
echo   Export Time: %YYYY%-%MM%-%DD% %HH%:%Min%:%Sec%
echo   Final File: %zip_file%

REM Show file size
for %%F in ("%zip_file%") do set final_size=%%~zF
echo   File Size: %final_size% bytes

REM Convert bytes to MB for easier reading
set /a size_mb=%final_size%/1048576
if %size_mb% GTR 0 (
    echo   File Size: ~%size_mb% MB
)

echo.
echo What was exported:
echo ✓ All database tables with complete structure
echo ✓ All data (SKUs, sales history, inventory, configurations)
echo ✓ All views and database functions
echo ✓ All triggers and procedures
echo ✓ All indexes and constraints
echo.

echo Next Steps:
echo 1. Transfer %zip_file% to your production server
echo 2. On the server, run: scripts/migration_toolkit/import_to_server.sh %zip_file%
echo 3. Verify the import with: python scripts/migration_toolkit/verify_migration.py
echo.

echo Transfer Methods:
echo • USB Drive: Copy file to USB and transfer manually
echo • Network Share: Copy to shared network folder
echo • Cloud Storage: Upload to Google Drive, Dropbox, etc.
echo • SCP/SFTP: scp %zip_file% user@server:/tmp/
echo.

echo File Location: %CD%\%zip_file%
echo.

REM Check if this is likely a test run (small file) or production (larger file)
if %final_size% LSS 102400 (
    echo NOTE: Small file size detected (less than 100KB)
    echo This suggests you may not have much data yet.
    echo This is normal for testing or initial setup.
) else (
    echo Good: File size suggests you have actual data to migrate.
)

echo.
echo ===============================================
echo Export tool completed successfully!
echo ===============================================
echo.
pause