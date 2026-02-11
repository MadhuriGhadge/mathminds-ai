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
    Tool for fetching live data from websites using Playwright.
    Useful for queries requiring real-time context (e.g., stock prices, weather, news).
    """

    def __init__(self, headless: bool = True):
        self.headless = headless
        # We use a ProcessPoolExecutor to run Playwright in a separate process.
        # This is CRITICAL on Windows if the main process uses SelectorEventLoopPolicy,
        # as Playwright requires ProactorEventLoopPolicy.
        self.executor = ProcessPoolExecutor(max_workers=1)

    async def scrape(self, query: str, extraction_focus: Optional[str] = None) -> Dict[str, Any]:
        """
        Scrapes data relevant to the query.
        runs the scraping logic in a separate process.
        
        Args:
            query: The search query or URL.
            extraction_focus: Optional keyword to focus extraction on.
        """
        logger.info(f"WebScraper triggered for query: {query}, focus: {extraction_focus}")
        
        loop = asyncio.get_running_loop()
        
        # Run in separate process
        try:
            result = await loop.run_in_executor(
                self.executor, 
                functools.partial(run_playwright_sync, query, self.headless, extraction_focus)
            )
            return result
        except Exception as e:
            logger.error(f"Process execution failed: {e}")
            return {
                "source": "web_scraper",
                "error": f"Process execution failed: {str(e)}",
                "status": "error"
            }
