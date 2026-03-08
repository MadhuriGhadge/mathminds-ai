import asyncio
import os
os.environ["DISABLE_MODEL_SOURCE_CHECK"] = "True"
import json
import sys

# Add current dir to path
sys.path.append(os.getcwd())

from app.core.orchestrator import Orchestrator

async def test_stream():
    # Mock dependencies
    orch = Orchestrator()
    print("Orchestrator initialized.")
    
    query = "what is 9^3?"
    print(f"Solving: {query}")
    
    try:
        async for event in orch.solve_problem_stream(query=query, request_id="test-rid"):
            print(f"EVENT: {event}")
    except Exception as e:
        print(f"FAILED: {e}")

if __name__ == "__main__":
    asyncio.run(test_stream())
