import logging
from app.worker.celery_app import celery_app

logger = logging.getLogger(__name__)

@celery_app.task(name="app.worker.tasks.scrape_task", bind=True)
def scrape_task(self, query: str, headless: bool = True, extraction_focus: str = None):
    """
    Legacy scraper task. Web search has been migrated to Native Gemini Grounding.
    This task is now a placeholder to maintain backward compatibility with any remaining calls.
    """
    logger.info(f"Scrape task {self.request.id} called for: {query} (Legacy/No-Op)")
    return {
        "source": "web_scraper_legacy",
        "content": "Notice: Web search has been migrated to Native Gemini Grounding. Use the web_search tool directly.",
        "status": "success",
        "url": "N/A"
    }
