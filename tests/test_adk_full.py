
import asyncio
import os
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the new agent
from app.agents.adk_mathminds import MathMindsADKAgent

async def main():
    print("Initializing MathMinds ADK Agent...")
    
    try:
        agent = MathMindsADKAgent()
        
        # Test 1: Math Problem
        prompt_math = "Calculate the derivative of x^2 + 5x."
        print(f"\nUser: {prompt_math}")
        response_math = await agent.solve(prompt_math)
        print(f"Agent Response: {response_math}")
        
        # Test 2: General Knowledge (Web Search)
        # Note: Web scraping might fail if not configured or blocked, but agent should handle it gracefully.
        prompt_search = "What is the capital of France?"
        print(f"\nUser: {prompt_search}")
        response_search = await agent.solve(prompt_search)
        print(f"Agent Response: {response_search}")

    except Exception as e:
        logger.error(f"Test failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
