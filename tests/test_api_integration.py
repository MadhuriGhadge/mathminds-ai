
import asyncio
import os
import sys
import logging
from dotenv import load_dotenv

# Fix path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from app.core.orchestrator import Orchestrator

async def main():
    print("Initializing Orchestrator...")
    try:
        orchestrator = Orchestrator()
        
        # Test: Arithmetic via Agent
        prompt = "Calculate 15 * 3."
        print(f"\nUser: {prompt} (Preference: agent)")
        
        result = await orchestrator.process_problem(
            text=prompt,
            model_preference="agent",
            request_id="test_req_1"
        )
        
        print("\nResult:")
        print(f"Status: {result.get('status')}")
        print(f"Source: {result.get('source')}")
        print(f"Answer: {result.get('answer')}")
        print(f"Model: {result.get('metadata', {}).get('model')}")
        
        if result.get("source") == "google_adk_agent":
            print("\nSUCCESS: Routed to Google ADK Agent.")
        else:
            print("\nFAILURE: Did not route to Google ADK Agent.")

    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
