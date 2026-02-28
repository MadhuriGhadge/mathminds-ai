import logging
from app.worker.celery_app import celery_app
from app.tools.web_scraper import run_playwright_sync

logger = logging.getLogger(__name__)

@celery_app.task(name="app.worker.tasks.scrape_task", bind=True)
def scrape_task(self, query: str, headless: bool = True, extraction_focus: str = None):
    """
    Celery task for web scraping.
    """
    logger.info(f"Task {self.request.id} started for query: {query}")
    try:
        result = run_playwright_sync(query, headless, extraction_focus)
        return result
    except Exception as e:
        logger.error(f"Task failed: {e}")
        return {
            "source": "web_scraper",
            "error": str(e),
            "status": "error"
        }
