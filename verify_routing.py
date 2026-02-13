
from app.core.orchestrator import Orchestrator

def test_routing():
    orch = Orchestrator()
    
    # Test cases
    queries = [
        ("calculate 2+2", True), # Simple
        ("solve x+5=10", True),  # Simple
        ("what is the probability of drawing a red card?", False), # Complex (Probability)
        ("integrate x^2", False), # Complex (Calculus)
        ("calculate the sum of limits", False) # Complex (Limit)
    ]
    
    print("--- Verifying Routing Logic ---")
    all_passed = True
    for q, expected_simple in queries:
        is_simple = orch._is_simple_problem(q)
        status = "✅" if is_simple == expected_simple else "❌"
        if not is_simple == expected_simple:
            all_passed = False
        print(f"{status} Query: '{q}' -> Is Simple? {is_simple} (Expected: {expected_simple})")
        
    if all_passed:
        print("\n✅ All routing checks passed!")
    else:
        print("\n❌ Use verify_routing.py to debug failures.")

if __name__ == "__main__":
    test_routing()
