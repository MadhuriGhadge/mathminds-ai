@echo off
echo Starting FastAPI Server...
call .venv\Scripts\activate
uvicorn app.api.main:app --reload --host 0.0.0.0 --port 8000
pause
