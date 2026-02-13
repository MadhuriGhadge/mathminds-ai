import os
import asyncio
from celery import Celery
from app.core.settings import settings
from app.tools.web_scraper import WebScraper
import logging

# Configure Logging
logger = logging.getLogger(__name__)

# Initialize Celery
celery_app = Celery(
    "mathminds_worker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

@celery_app.task(name="scrape_web_task", bind=True)
def scrape_web_task(self, query: str, focus: str = ""):
    """
    Celery task to run web scraping in a background worker.
    Since Playwright is async/sync hybrid, we run the sync version here
    or manage the loop carefully.
    """
    logger.info(f"Worker: Starting scrape for '{query}'")
    
    # We use the sync logic of the scraper tools or run the async one via asyncio.run
    # For simplicity/stability in Celery, we'll instantiate the scraper and run.
    
    # Note: WebScraper class uses ProcessPoolExecutor internally for safety on Windows
    # Here we are already in a worker process, so we can just run it.
    
    scraper = WebScraper(headless=True)
    
    # Run async scrape in this sync task
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(scraper.scrape(query, extraction_focus=focus))
        loop.close()
        return result
    except Exception as e:
        logger.error(f"Worker Scrape Failed: {e}")
        return {"error": str(e), "status": "error"}

@celery_app.task(name="solve_heavy_math_task")
def solve_heavy_math_task(problem_text: str):
    """
    Placeholder for really heavy symbolic computation if needed.
    """
    pass
