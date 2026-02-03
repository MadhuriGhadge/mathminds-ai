import logging
import asyncio
from typing import Optional, Dict, Any
from playwright.sync_api import sync_playwright
from concurrent.futures import ProcessPoolExecutor
import functools

logger = logging.getLogger(__name__)

def run_playwright_sync(query: str, headless: bool, extraction_focus: Optional[str] = None) -> Dict[str, Any]:
    """
    Standalone function to run Playwright in a separate process.
    Must be top-level for pickling.
    """
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)
            # Use a standard user agent to avoid immediate blocking
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            )
            page = context.new_page()
            
            try:
                # Targeted Scraping Logic
                q_lower = query.lower()
                if query.startswith("http"):
                     search_url = query
                elif "gold" in q_lower and ("rate" in q_lower or "price" in q_lower):
                     # India-specific context given user's query history, but goodreturns is generally accessible
                     search_url = "https://www.goodreturns.in/gold-rates/"
                elif "weather" in q_lower:
                     # wttr.in is perfect for text-based weather
                     # Extract location if possible, otherwise default (IP based) or specific
                     # Simple heuristic: remove 'weather', 'in', 'at'
                     location = q_lower.replace("weather", "").replace(" in ", "").replace(" at ", "").strip()
                     search_url = f"https://wttr.in/{location}?format=3" if location else "https://wttr.in/?format=3"
                elif "stock" in q_lower or "share" in q_lower:
                     # Yahoo Finance Search
                     search_url = f"https://finance.yahoo.com/lookup?s={query}"
                else:
                     # Fallback to DuckDuckGo (HTML version for easier scraping), or Google if preferred
                     search_url = f"https://html.duckduckgo.com/html/?q={query}"
                
                logger.info(f"Attempting to scrape: {search_url}")
                page.goto(search_url, timeout=30000, wait_until="domcontentloaded")
            
            except Exception as e:
                logger.warning(f"Primary search failed for {query}: {e}. Falling back to DuckDuckGo.")
                search_url = f"https://html.duckduckgo.com/html/?q={query}"
                page.goto(search_url, timeout=30000, wait_until="domcontentloaded")
            
            # Extract main content
            content = page.inner_text("body")
            
            final_content = ""
            
            if extraction_focus:
                # Targeted Extraction
                # Find all occurrences of the focus keyword (case-insensitive)
                import re
                # Escape the focus term just in case
                pattern = re.compile(re.escape(extraction_focus), re.IGNORECASE)
                matches = list(pattern.finditer(content))
                
                if matches:
                    chunks = []
                    for m in matches[:5]: # limit to top 5 matches
                        start = max(0, m.start() - 300)
                        end = min(len(content), m.end() + 300)
                        chunk = content[start:end].replace("\n", " ")
                        chunks.append(f"...{chunk}...")
                    final_content = "\n\n".join(chunks)
                else:
                    # Fallback if focus not found
                    final_content = content[:2000] + "\n[Note: Extraction focus not found in top content]"
            else:
                 # Basic cleaning - top 5000 chars
                final_content = content[:5000]
            
            browser.close()
            
            return {
                "source": "web_scraper",
                "url": search_url,
                "content": final_content,
                "status": "success"
            }

    except Exception as e:
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
