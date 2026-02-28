import logging
import asyncio
from typing import Optional, Dict, Any
from playwright.sync_api import sync_playwright
import functools
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from concurrent.futures import ProcessPoolExecutor

logger = logging.getLogger(__name__)

def run_playwright_sync(query: str, headless: bool, extraction_focus: Optional[str] = None) -> Dict[str, Any]:
    """
    Scrapes a webpage associated with the query using Playwright with anti-detection measures.
    Uses BeautifulSoup for robust text extraction.
    """
    ua = UserAgent()
    user_agent = ua.random
    
    try:
        # Check if an event loop is already running in this thread
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                 # We are in an asyncio loop! We must use a thread or process.
                 # For Celery tasks, this shouldn't happen with solo/prefork,
                 # but for local testing it does.
                 pass
        except RuntimeError:
            pass

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)
            context = browser.new_context(
                user_agent=user_agent,
                viewport={"width": 1280, "height": 720}
            )
            page = context.new_page()
            
            # Determine URL Logic
            q_lower = query.lower()
            if query.startswith("http"):
                 search_url = query
            elif "gold" in q_lower and ("rate" in q_lower or "price" in q_lower):
                 search_url = "https://www.goodreturns.in/gold-rates/"
            elif "weather" in q_lower:
                 # Clean location logic
                 location = q_lower.replace("weather", "").replace(" in ", "").replace(" at ", "").strip()
                 search_url = f"https://wttr.in/{location}?format=3" if location else "https://wttr.in/?format=3"
            elif "stock" in q_lower or "share" in q_lower:
                 search_url = f"https://finance.yahoo.com/lookup?s={query}"
            else:
                 search_url = f"https://html.duckduckgo.com/html/?q={query}"
            
            logger.info(f"Scraping: {search_url} | UA: {user_agent}")
            
            try:
                page.goto(search_url, timeout=30000, wait_until="domcontentloaded")
            except Exception as e:
                logger.warning(f"Primary nav failed: {e}. Fallback to DDG.")
                search_url = f"https://html.duckduckgo.com/html/?q={query}"
                page.goto(search_url, timeout=30000, wait_until="domcontentloaded")
            
            # Content Extraction via BeautifulSoup
            html_content = page.content()
            soup = BeautifulSoup(html_content, "html.parser")
            
            # Remove junk elements
            for script in soup(["script", "style", "nav", "footer", "header", "noscript", "svg"]):
                script.decompose()

            # Get clean text
            text = soup.get_text(separator="\n", strip=True)
            
            final_content = ""
            if extraction_focus:
                # Basic targeted extraction (could be improved with regex or embedding search)
                lines = text.split("\n")
                relevant_lines = [line for line in lines if extraction_focus.lower() in line.lower()]
                if relevant_lines:
                    final_content = "\n".join(relevant_lines[:20]) # Limit relevant lines
                else:
                    final_content = text[:2000] + "\n[Note: Focus term not found]"
            else:
                 final_content = text[:5000]
            
            browser.close()
            
            return {
                "source": "web_scraper",
                "url": search_url,
                "content": final_content,
                "status": "success"
            }

    except Exception as e:
        logger.error(f"Scraping error: {e}")
        return {
            "source": "web_scraper",
            "error": str(e),
            "status": "error"
        }

class WebScraper:
    """
    Tool for fetching live data from websites using a Celery task queue.
    Offloads heavy browser automation to dedicated workers.
    """

    def __init__(self, headless: bool = True):
        self.headless = headless

    async def scrape(self, query: str, extraction_focus: Optional[str] = None) -> Dict[str, Any]:
        """
        Dispatches a scraping task to Celery and waits for the result.
        """
        logger.info(f"WebScraper: Dispatching Celery task for query: {query}")
        
        try:
            from app.worker.tasks import scrape_task
            
            # Dispatch to worker
            task = scrape_task.delay(query, self.headless, extraction_focus)
            
            # Wait for result (blocking the coroutine, but not the event loop)
            # We use a loop/sleep or better, run_in_executor to not block the event loop if .get() is blocking.
            # Celery's AsyncResult.get() is blocking.
            
            import asyncio
            for _ in range(30): # 30 seconds timeout
                if task.ready():
                    return task.result
                await asyncio.sleep(1)
            
            return {
                "source": "web_scraper",
                "error": "Scraping task timed out in worker queue.",
                "status": "error"
            }
            
        except Exception as e:
            logger.error(f"Celery dispatch failed: {e}")
            return {
                "source": "web_scraper",
                "error": f"Celery dispatch failed: {str(e)}",
                "status": "error"
            }
