import logging
import sys
import os

# Add the current directory to sys.path so we can import 'app'
sys.path.append(os.getcwd())

from app.tools.web_scraper import run_playwright_sync

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_direct_scrape():
    print("--- Testing run_playwright_sync DIRECTLY (Subprocess-safe) ---")
    query = "current gold rate in mumbai"
    
    try:
        # We run it synchronously as it's designed
        result = run_playwright_sync(query, headless=True)
        
        print("\n[RESULT]")
        if result.get("status") == "success":
            print(f"URL: {result.get('url')}")
            print(f"Content Length: {len(result.get('content', ''))}")
            print(f"Sample: {result.get('content')[:500]}...")
        else:
            print(f"Error: {result.get('error')}")
            
    except Exception as e:
        print(f"Crashed: {e}")

if __name__ == "__main__":
    test_direct_scrape()
