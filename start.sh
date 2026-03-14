#!/bin/bash

# Start Celery worker in the background
celery -A app.worker.celery_app worker --loglevel=info &

# Start FastAPI backend in the background
uvicorn app.api.main:app --host 0.0.0.0 --port 8000 &

# Start Streamlit frontend on port 7860 (Hugging Face default)
streamlit run frontend/app.py --server.port 7860 --server.address 0.0.0.0
