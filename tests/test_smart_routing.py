import asyncio
import logging
import sys
import os

if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.orchestrator import Orchestrator

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_routing():
    print("Initializing Orchestrator...")
    # Mock cache/db to avoid needing real redis/mongo for this unit test
    class MockManager:
        def get_cached_answer(self, hash): return None
        def set_cached_answer(self, hash, ans): pass
        def set_if_not_exists(self, hash, ans): pass
        def find_by_hash(self, hash): return None
        def save_problem(self, data, solu): pass
        
    orch = Orchestrator(cache_manager=MockManager(), db_manager=MockManager())
    
    # Test 1: Web Route
    query_web = "What is the current stock price of Google?"
    print(f"\n--- Testing Web Route: '{query_web}' ---")
    # We might fail on playwright invoke if not installed, but let's check the route log/metadata
    # To avoid full execution failure, we might mock tools too, but we want to see if `process_problem` calls them.
    # Actually, let's just run it. If playwright fails, we'll see the error but we can check if it TRIED.
    
    try:
        res_web = await orch.process_problem(text=query_web)
        print(f"Result Status: {res_web['status']}")
        print(f"Metadata Route: {res_web.get('metadata', {}).get('route')}")
        # Check if tool context was seemingly added (via answer or logs)
        # Since we don't return tool context directly in result, check logs or side effects?
        # Actually, Orchestrator appends it to prompt, but doesn't return it in 'answer' directly unless Gemini uses it.
        # But we logged "Executing Web Scraper..."
    except Exception as e:
        print(f"Web Route Execution Failed (Expected if browsers missing): {e}")

    # Test 2: Symbolic Route
    query_sym = "integrate x^2"
    print(f"\n--- Testing Symbolic Route: '{query_sym}' ---")
    try:
        res_sym = await orch.process_problem(text=query_sym)
        print(f"Result Status: {res_sym['status']}")
        print(f"Metadata Route: {res_sym.get('metadata', {}).get('route')}")
    except Exception as e:
        print(f"Symbolic Route Execution Failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_routing())
