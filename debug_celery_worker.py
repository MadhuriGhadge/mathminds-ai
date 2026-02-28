import asyncio
import logging
import sys
import os

# Add the current directory to sys.path so we can import 'app'
sys.path.append(os.getcwd())

from app.worker.tasks import scrape_task
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def debug_scrape():
    print("Triggering Celery Scrape Task...")
    query = "gold rate in india today"
    
    try:
        # Dispatch task
        result = scrape_task.delay(query)
        print(f"Task ID: {result.id}")
        
        # Wait for result
        start_time = time.time()
        max_wait = 60 # seconds
        
        while time.time() - start_time < max_wait:
            if result.ready():
                print("Task Ready!")
                print("Result Status:", result.status)
                # Safely handle potential encoding issues when printing to console
                try:
                    res_content = str(result.result)
                    print("Result Content (partial):", res_content[:200].encode('ascii', 'ignore').decode('ascii'))
                except Exception as e:
                    print(f"Result received, but print failed: {e}")
                return
            
            print(f"Waiting... (status: {result.status})")
            await asyncio.sleep(2)
            
        print("Task timed out. Is the worker running?")
        
    except Exception as e:
        print(f"Dispatch failed: {e}")

if __name__ == "__main__":
    asyncio.run(debug_scrape())
