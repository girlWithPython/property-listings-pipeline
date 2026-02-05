@echo off
echo ================================================
echo  Rightmove Scraper - MinIO System Startup
echo ================================================
echo.

echo [1/4] Installing Python dependencies...
pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install dependencies
    pause
    exit /b 1
)
echo.

echo [2/4] Starting Docker containers...
docker-compose up -d
if errorlevel 1 (
    echo ERROR: Failed to start Docker containers
    echo Make sure Docker Desktop is running
    pause
    exit /b 1
)
echo.

echo [3/4] Waiting for services to be ready...
timeout /t 10 /nobreak > nul
echo.

echo [4/4] Testing MinIO connection...
python test_minio_setup.py
if errorlevel 1 (
    echo WARNING: MinIO test failed
    echo Check the logs above for details
) else (
    echo.
    echo ================================================
    echo  System is ready!
    echo ================================================
    echo.
    echo Services running:
    echo  - Redis:      localhost:6379
    echo  - MinIO API:  localhost:9000
    echo  - MinIO UI:   http://localhost:9001
    echo.
    echo To start scraping:
    echo   python -m scraper.run
    echo.
    echo To view worker logs:
    echo   docker-compose logs -f celery_worker
    echo.
    echo To stop all services:
    echo   docker-compose down
    echo.
)

pause
