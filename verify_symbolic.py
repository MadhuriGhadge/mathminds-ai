
import asyncio
import sys
import os
import logging
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
    print("🚀 Starting Symbolic Solver Verification...")
    orchestrator = Orchestrator()
    
    test_cases = [
        "Calculate 152 * 139", # Unique
        "Solve 4x + 12 = 32", # Unique
        "derivative of x^4", # Unique
        "Explain limits" # Should NOT be deterministic
    ]
    
    for query in test_cases:
        print(f"\n--- Testing: {query} ---")
        try:
            result = await orchestrator.process_problem(text=query)
            
            source = result.get("metadata", {}).get("source")
            model = result.get("metadata", {}).get("model_used")
            latency = result.get("metadata", {}).get("latency", 0)
            answer = result.get("answer", {})
            
            p_source = "✅" if source == "deterministic" else "❌"
            if query == "Explain limits":
                p_source = "✅" if source != "deterministic" else "❌"

            print(f"Source: {source} {p_source}")
            print(f"Model: {model}")
            print(f"Latency: {latency:.4f}s")
            print(f"Answer Keys: {list(answer.keys())}")
            print(f"Content: {answer.get('text') or answer.get('answer') or answer}")
            
        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(verify())
