@echo off
echo Starting MathMinds API (Windows Production Mode)...

:: Check for Redis (Optional check, just warning)
echo Ensure Redis and MongoDB are running locally!

:: Set PYTHONPATH
set PYTHONPATH=%PYTHONPATH%;%cd%

:: Run Uvicorn with workers
:: Note: Gunicorn is not supported on Windows. We use Uvicorn directly with workers.
echo Starting Uvicorn with 4 workers...
uvicorn app.api.main:app --host 0.0.0.0 --port 8000 --workers 4

pause
