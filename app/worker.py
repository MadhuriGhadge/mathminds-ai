import os
import logging
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

# Global orchestrator for the worker process
# Initialized lazily to avoid issues during import or if worker just starts up
_orchestrator = None

def get_orchestrator():
    """Lazily initializes and returns the orchestrator instance."""
    global _orchestrator
    if _orchestrator is None:
        try:
            logger.info("Initializing Orchestrator in Celery worker...")
            _orchestrator = Orchestrator()
        except Exception as e:
            logger.critical(f"Failed to initialize Orchestrator in worker: {e}")
            raise
    return _orchestrator

@celery_app.task(name="solve_problem_task", bind=True, acks_late=True)
def solve_problem_task(self, user_input: str):
    """
    Celery task to asynchronously solve a math problem.
    """
    try:
        orchestrator = get_orchestrator()
        result = orchestrator.process_problem(user_input)
        return result
    except Exception as e:
        logger.error(f"Error in solve_problem_task: {e}")
        # Optionally retry
        # raise self.retry(exc=e, countdown=5, max_retries=3)
        return {"status": "error", "error": str(e)}
