import os
import logging
import uuid
from celery import Celery
from app.core.orchestrator import Orchestrator

# Configure logging
logger = logging.getLogger(__name__)

# Configure Celery
# Broker and Backend URL from env or default to localhost redis
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "mathminds_worker",
    broker=REDIS_URL,
    backend=REDIS_URL
)

# Optional configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
)

from app.api.deps import get_orchestrator as _get_shared_orchestrator

def get_orchestrator():
    """Lazily initializes and returns the orchestrator instance (via shared deps)."""
    # Using the shared dependency provider ensures connection pooling
    return _get_shared_orchestrator()

@celery_app.task(name="solve_problem_task", bind=True, acks_late=True)
def solve_problem_task(self, user_input: str, request_id: str = None):
    """
    Celery task to asynchronously solve a math problem.
    """
    if not request_id:
        request_id = str(uuid.uuid4())
        
    try:
        orchestrator = get_orchestrator()
        result = orchestrator.process_problem(user_input, request_id=request_id)
        return result
    except Exception as e:
        logger.error(f"[{request_id}] Error in solve_problem_task: {e}")
        # Optionally retry
        # raise self.retry(exc=e, countdown=5, max_retries=3)
        return {"status": "error", "error": str(e), "metadata": {"request_id": request_id, "stage": "worker"}}
