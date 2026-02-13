@echo off
echo Starting Celery Worker...
call .venv\Scripts\activate
celery -A app.worker.celery_app worker --loglevel=info --pool=solo
pause
