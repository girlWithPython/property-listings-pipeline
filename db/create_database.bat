@echo off
echo Creating PostgreSQL database 'scraper'...
echo.

REM Try common PostgreSQL installation paths
set PSQL_PATH=""

if exist "C:\Program Files\PostgreSQL\16\bin\psql.exe" (
    set PSQL_PATH="C:\Program Files\PostgreSQL\16\bin\psql.exe"
) else if exist "C:\Program Files\PostgreSQL\15\bin\psql.exe" (
    set PSQL_PATH="C:\Program Files\PostgreSQL\15\bin\psql.exe"
) else if exist "C:\Program Files\PostgreSQL\14\bin\psql.exe" (
    set PSQL_PATH="C:\Program Files\PostgreSQL\14\bin\psql.exe"
) else if exist "C:\Program Files\PostgreSQL\13\bin\psql.exe" (
    set PSQL_PATH="C:\Program Files\PostgreSQL\13\bin\psql.exe"
)

if %PSQL_PATH%=="" (
    echo ERROR: PostgreSQL not found in common installation paths
    echo Please run this command manually in psql or pgAdmin:
    echo.
    echo     CREATE DATABASE scraper;
    echo.
    pause
    exit /b 1
)

echo Found PostgreSQL at: %PSQL_PATH%
echo.

REM Create the database
%PSQL_PATH% -U postgres -c "CREATE DATABASE scraper;"

if %ERRORLEVEL% EQU 0 (
    echo.
    echo SUCCESS: Database 'scraper' created!
    echo You can now run: python -m scraper.run
) else (
    echo.
    echo ERROR: Failed to create database
    echo Please create it manually using pgAdmin or psql
)

echo.
pause
