
import asyncio
import sys
import os
import logging
import traceback
from dotenv import load_dotenv

# Load env vars
load_dotenv(override=True)

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Windows asyncio policy
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from app.core.orchestrator import Orchestrator

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("debugger")

async def reproduce():
    print("Attempting to reproduce crash with 'solve 4x=36'...")
    try:
        orchestrator = Orchestrator()
        
        # Test case that crashed for user - force new hash
        import time
        query = f"solve 4x=36 {int(time.time())}" # Add timestamp to bypass cache
        # Wait, adding timestamp breaks "solve" logic? 
        # "solve 4x=36 12345" might fail the regex?
        # Better: Disable cache in settings temporarily?
        # Or just clear cache first.
        # Or just query = "solve 4x=36" and I clear cache in script.
        
        from app.core.settings import settings
        settings.ENABLE_CACHE = False
        
        query = "solve 4x=36"
        
        print(f"Executing: {query}")
        result = await orchestrator.process_problem(text=query)
        
        print("Finished without crash.")
        print(f"Result: {result.get('answer')}")
        
    except Exception as e:
        print(f"Exception caught in main loop: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    try:
        asyncio.run(reproduce())
    except KeyboardInterrupt:
        print("Interrupted")
    except Exception as e:
        print(f"Fatal crash: {e}")
        traceback.print_exc()
