
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import logging

logger = logging.getLogger(__name__)

class SeleniumScraper:
    """
    Fallback scraper using Selenium for sites where Playwright fails.
    """

    def __init__(self, headless: bool = True):
        self.headless = headless
        self.driver = None

    def _setup_driver(self):
        """
        Initialize Chrome Driver.
        """
        try:
            options = Options()
            if self.headless:
                options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            
            # Auto-install driver
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=options)
        except Exception as e:
            logger.error(f"Failed to setup Selenium driver: {e}")
            raise e

    def scrape(self, url: str) -> str:
        """
        Scrape a URL and return page source.
        """
        if not self.driver:
            self._setup_driver()

        try:
            logger.info(f"Selenium scraping: {url}")
            self.driver.get(url)
            # Add explicit waits if needed
            return self.driver.page_source
        except Exception as e:
            logger.error(f"Selenium scrape failed: {e}")
            return ""
        finally:
            # For simplistic usage, we might close after each scrape or keep open.
            # Here we close to save resources as it's a fallback.
            if self.driver:
                self.driver.quit()
                self.driver = None
