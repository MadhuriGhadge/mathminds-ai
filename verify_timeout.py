
import asyncio
import sys
import os
import logging
import time
from dotenv import load_dotenv

# Load env vars
load_dotenv(override=True)

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from app.core.orchestrator import Orchestrator

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verifier")

async def verify():
    print("Starting Timeout Verification...")
    orchestrator = Orchestrator()
    
    # "3+5" should be instant. 
    # If it was blocking, this script would hang or take > 2s per call if we were simulating high load, 
    # but here we just want to ensure it RETURNS success and definitely < 2s.
    
    test_cases = [
        "calculate 100+55", # Unique
        "solve 4z=20", # Unique
    ]
    
    for query in test_cases:
        print(f"\n--- Testing: {query} ---")
        start = time.time()
        try:
            result = await orchestrator.process_problem(text=query)
            duration = time.time() - start
            
            source = result.get("metadata", {}).get("source")
            latency = result.get("metadata", {}).get("latency", 0)
            answer = result.get("answer", {})
            
            print(f"Source: {source} (Expected: deterministic/cache)")
            print(f"Latency: {latency:.4f}s")
            print(f"Total Duration: {duration:.4f}s")
            
            if duration > 2.5:
                print("❌ FAILED: Took too long (Blocking?)")
            else:
                print("✅ PASSED: Fast execution")
            
            print(f"Content: {answer.get('text') or answer.get('answer') or answer}")
            
        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(verify())
