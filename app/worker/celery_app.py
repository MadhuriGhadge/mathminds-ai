from celery import Celery
import os
from app.core.settings import settings

# Initialize Celery
celery_app = Celery(
    "mathminds",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.worker.tasks"]
)

# Optional configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300, # 5 minutes max
)

if __name__ == "__main__":
    celery_app.start()
