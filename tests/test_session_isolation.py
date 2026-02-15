
import sys
import os
sys.path.insert(0, os.getcwd())

import pytest
import asyncio
from app.agents.adk_mathminds import MathMindsADKAgent

@pytest.mark.asyncio
async def test_session_isolation():
    """
    Verifies that the ADK agent maintains separate conversation histories 
    for different session IDs.
    """
    agent = MathMindsADKAgent()
    
    user_id = "test_user_isolation"
    session_a = "session_A"
    session_b = "session_B"

    print("\n--- Starting Session Isolation Test ---")

    # 1. Seed Session A
    print(f"Seeding {session_a} with context 'My name is Alice'...")
    resp_a1 = await agent.solve(
        problem="My name is Alice. Remember this.",
        session_id=session_a,
        user_id=user_id
    )
    print(f"Agent response (A1): {resp_a1}")

    # 2. Seed Session B
    print(f"Seeding {session_b} with context 'My name is Bob'...")
    resp_b1 = await agent.solve(
        problem="My name is Bob. Remember this.",
        session_id=session_b,
        user_id=user_id
    )
    print(f"Agent response (B1): {resp_b1}")

    # 3. Query Session A
    print(f"Querying {session_a} for name...")
    resp_a2 = await agent.solve(
        problem="What is my name?",
        session_id=session_a,
        user_id=user_id
    )
    print(f"Agent response (A2): {resp_a2}")
    
    # 4. Query Session B
    print(f"Querying {session_b} for name...")
    resp_b2 = await agent.solve(
        problem="What is my name?",
        session_id=session_b,
        user_id=user_id
    )
    print(f"Agent response (B2): {resp_b2}")

    # Assertions
    assert "Alice" in resp_a2, f"Session A failed to remember Alice. Got: {resp_a2}"
    assert "Bob" in resp_b2, f"Session B failed to remember Bob. Got: {resp_b2}"
    assert "Bob" not in resp_a2, "Session A leaked context from Session B!"
    assert "Alice" not in resp_b2, "Session B leaked context from Session A!"

    print("\nSUCCESS: Sessions are isolated correctly!")

if __name__ == "__main__":
    asyncio.run(test_session_isolation())
