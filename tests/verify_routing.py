import asyncio
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.orchestrator import Orchestrator, IntentType

async def test_routing():
    print("Initializing Orchestrator...")
    orchestrator = Orchestrator()
    
    test_cases = [
        ("2 + 2", IntentType.ARITHMETIC),
        ("solve x^2 + 2x + 1 = 0", IntentType.SYMBOLIC_MATH),
        ("price of bitcoin", IntentType.SEARCH),
        ("explain quantum physics", IntentType.CONCEPTUAL),
        ("", IntentType.UNKNOWN)
    ]
    
    print("\n--- Testing Classification Logic ---")
    for text, expected in test_cases:
        intent = orchestrator._classify_intent(text, has_image=False)
        status = "✅" if intent == expected else f"❌ (Got {intent})"
        print(f"Input: '{text}' -> {expected.value} : {status}")

    print("\n--- Testing Execution (Dry Run) ---")
    # We won't run full execution to avoid API costs/time, just check classification for now
    # But let's run one simple arithmetic to see the full flow
    
    print("Running full flow for '50 + 50'...")
    try:
        result = await orchestrator.process_problem(text="50 + 50")
        print(f"Result Status: {result['status']}")
        print(f"Source: {result['source']}")
        print(f"Answer: {result['answer']}")
        
        if result['source'] == "symbolic_solver" and result['answer'] == "100":
             print("✅ Arithmetic Routing Success")
        else:
             print("❌ Arithmetic Routing Failed")
             
    except Exception as e:
        print(f"Execution failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_routing())
