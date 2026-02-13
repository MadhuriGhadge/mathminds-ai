import asyncio
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from app.tools.web_scraper import WebScraper

async def main():
    print("Initializing WebScraper...")
    scraper = WebScraper(headless=True) 
    
    print("\n--- Test 1: Generic Search (Yahoo Finance via Logic) ---")
    # Logic in scraper: if "stock" in query -> yahoo finance
    query1 = "stock price of apple"
    print(f"Query: {query1}")
    result1 = await scraper.scrape(query1)
    print(f"Status: {result1.get('status')}")
    if result1.get('error'):
        print(f"Error: {result1.get('error')}")
    else:
        content = result1.get('content', '')
        print(f"Content Length: {len(content)}")
        print(f"Preview: {content[:200]}...")

    print("\n--- Test 2: Gold Rate (Goodreturns via Logic) ---")
    # Logic in scraper: if "gold" and "rate" -> goodreturns
    query2 = "gold rate today"
    print(f"Query: {query2}")
    result2 = await scraper.scrape(query2)
    print(f"Status: {result2.get('status')}")
    if result2.get('error'):
        print(f"Error: {result2.get('error')}")
    else:
         content = result2.get('content', '')
         print(f"Content Length: {len(content)}")
         print(f"Preview: {content[:200]}...")

if __name__ == "__main__":
    asyncio.run(main())
