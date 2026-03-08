import asyncio
import logging
from app.tools.web_scraper import run_playwright_sync

logging.basicConfig(level=logging.INFO)

def test_scraper():
    print("Starting WebScraper Verification...")
    
    # Test query: something that definitely has tables
    query = "gold rate in bangalore"
    print(f"Query: {query}")
    
    result = run_playwright_sync(query, headless=True)
    
    if result.get("status") == "success":
        print(f"Success! Targeted URL: {result.get('url')}")
        content = result.get("content", "")
        
        # Check for Table Preservation
        has_tables = "[TABLE START]" in content
        print(f"Table Preservation: {'DETECTED' if has_tables else 'NOT FOUND'}")
        
        # Check for dynamic search (should not be DuckDuckGo URL if successful)
        is_ddg = "duckduckgo" in result.get("url", "").lower()
        print(f"Dynamic Search: {'WORKING' if not is_ddg else 'FALLBACK TO DDG'}")
        
        print(f"Content Preview (first 200 chars):\n{content[:200]}...")
    else:
        print(f"Error: {result.get('error')}")

if __name__ == "__main__":
    test_scraper()
