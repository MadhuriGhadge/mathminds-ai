import logging
import asyncio
import re
import random
from typing import Optional, Dict, Any
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth
from bs4 import BeautifulSoup
from fake_useragent import UserAgent

logger = logging.getLogger(__name__)

def run_playwright_sync(query: str, headless: bool, extraction_focus: Optional[str] = None) -> Dict[str, Any]:
    """
    Refined Scraper with Stealth Mode:
    1. Stealth Integration: Uses playwright-stealth to bypass bot detection.
    2. Dynamic Search: Simulates human-like interaction on search engines.
    3. Table Preservation: Converts HTML tables to structured text.
    4. Anti-Detection: Enhanced headers, randomized delays, and metadata masking.
    """
    ua = UserAgent()
    user_agent = ua.chrome
    
    try:
        with sync_playwright() as p:
            # P1: Browser Launch
            browser = p.chromium.launch(headless=headless)
            
            # Create context with realistic window size and headers
            context = browser.new_context(
                user_agent=user_agent,
                viewport={"width": 1920, "height": 1080},
                device_scale_factor=1,
                has_touch=False,
                is_mobile=False,
                extra_http_headers={
                    "Accept-Language": "en-US,en;q=0.9",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                    "Sec-Fetch-Site": "none",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Dest": "document",
                    "Upgrade-Insecure-Requests": "1"
                }
            )
            
            page = context.new_page()
            
            # --- P0: APPLY STEALTH ---
            Stealth().apply_stealth_sync(page)
            
            # --- P1: IMPROVED NAVIGATION LOGIC ---
            target_url = None
            if query.startswith("http"):
                target_url = query
            else:
                try:
                    logger.info("Performing stealth search on DuckDuckGo...")
                    # Go to home page first to establish cookies/session
                    page.goto("https://duckduckgo.com/", wait_until="networkidle", timeout=30000)
                    
                    # Human-like delay before typing
                    page.wait_for_timeout(random.randint(500, 1500))
                    
                    search_input = 'input[name="q"]'
                    page.wait_for_selector(search_input, timeout=10000)
                    
                    # Simulate realistic typing speed
                    page.type(search_input, query, delay=random.randint(50, 200))
                    page.wait_for_timeout(random.randint(300, 700))
                    page.press(search_input, "Enter")
                    
                    # Wait for results
                    page.wait_for_load_state("networkidle", timeout=20000)
                    
                    # Robust search for result links
                    selectors = [
                        'a[data-testid="result-title-a"]', 
                        '#links .result__a', 
                        'h2 a',
                        '.result__url' # Backup
                    ]
                    
                    for selector in selectors:
                        try:
                            logger.info(f"Trying selector: {selector}")
                            first_link = page.wait_for_selector(selector, timeout=5000)
                            if first_link:
                                target_url = first_link.get_attribute("href")
                                if target_url: 
                                    logger.info(f"Found target_url: {target_url} using {selector}")
                                    break
                        except Exception:
                            continue
                            
                except Exception as e:
                    logger.warning(f"Stealth DDG search failed: {e}. Trying secondary fallback.")
                    # Use a clean direct search URL if interactive fails
                    target_url = f"https://duckduckgo.com/?q={query}"

            # CRITICAL: Ensure we have a URL to navigate to
            if not target_url:
                target_url = f"https://duckduckgo.com/?q={query}"
                logger.info(f"Final fallback to DDG search page: {target_url}")

            logger.info(f"Navigating to final target: {target_url}")

            # --- P0: PAGE NAVIGATION & CONTENT LOAD ---
            try:
                # Some sites need more time to execute JS after networkidle
                page.goto(target_url, timeout=45000, wait_until="networkidle")
                page.wait_for_timeout(random.randint(1000, 2000)) 
            except Exception as e:
                logger.warning(f"Deep network idle timeout on {target_url}, using DOM snapshot.")
                # If target_url is None, this will fail. Handled above.
                try:
                    page.goto(target_url, wait_until="domcontentloaded", timeout=15000)
                except Exception:
                    pass

            # --- P0: STRUCTURED CONTENT EXTRACTION ---
            html_content = page.content()
            soup = BeautifulSoup(html_content, "html.parser")
            
            # Remove purely visual/scripting elements
            for element in soup(["script", "style", "nav", "footer", "header", "noscript", "svg", "iframe", "button"]):
                element.decompose()

            # PRESERVE TABLES (Enhanced)
            for table in soup.find_all("table"):
                table_text = []
                # Handle headers if present
                thead = table.find("thead")
                if thead:
                    headers = [h.get_text(strip=True) for h in thead.find_all(["th", "td"])]
                    if any(headers):
                        table_text.append(" | ".join(headers))
                        table_text.append("-" * len(" | ".join(headers)))
                
                # Handle rows
                for row in table.find_all("tr"):
                    # Skip rows that are already handled in thead
                    if thead and row.parent == thead:
                        continue
                    cells = [cell.get_text(strip=True) for cell in row.find_all(["td", "th"])]
                    if any(cells): # Avoid empty rows
                        table_text.append(" | ".join(cells))
                
                if table_text:
                    table.replace_with("\n[TABLE START]\n" + "\n".join(table_text) + "\n[TABLE END]\n")

            # Get clean, structured text
            text = soup.get_text(separator="\n", strip=True)
            
            # Content Filtering
            if extraction_focus:
                lines = text.split("\n")
                pattern = re.compile(re.escape(extraction_focus), re.IGNORECASE)
                # Capture context (line before and after)
                relevant_content = []
                for i, line in enumerate(lines):
                    if pattern.search(line):
                        if i > 0: relevant_content.append(lines[i-1])
                        relevant_content.append(line)
                        if i < len(lines) - 1: relevant_content.append(lines[i+1])
                        relevant_content.append("-" * 10)
                
                if relevant_content:
                    final_content = "\n".join(relevant_content[:60]) # Larger snippet for context
                else:
                    final_content = text[:5000] + "\n[Note: Extraction focus term not found]"
            else:
                final_content = text[:10000] # Increased for better LLM performance

            browser.close()
            
            return {
                "source": "web_scraper",
                "url": str(target_url), # Ensure string for JSON safety
                "content": final_content,
                "status": "success"
            }

    except Exception as e:
        logger.error(f"Stealth scraping failed: {e}")
        return {"source": "web_scraper", "error": str(e), "status": "error"}

class WebScraper:
    def __init__(self, headless: bool = True):
        self.headless = headless

    async def scrape(self, query: str, extraction_focus: Optional[str] = None) -> Dict[str, Any]:
        """Dispatches the scraping task to the backround worker (Celery)"""
        logger.info(f"WebScraper: Initializing stealth scrape for: {query}")
        
        try:
            from app.worker.tasks import scrape_task
            task = scrape_task.delay(query, self.headless, extraction_focus)
            
            # Wait for result with a generous timeout (stealth takes longer)
            max_retries = 90 
            for _ in range(max_retries):
                if task.ready():
                    return task.result
                await asyncio.sleep(1)
            
            return {"source": "web_scraper", "error": "Worker timeout (Page was likely too heavy)", "status": "error"}
            
        except Exception as e:
            logger.warning(f"Worker unavailable, falling back to local thread: {e}")
            return await asyncio.to_thread(run_playwright_sync, query, self.headless, extraction_focus)
