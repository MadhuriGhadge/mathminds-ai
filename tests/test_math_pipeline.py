import asyncio
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from app.core.math_normalizer import MathQueryNormalizer
from app.tools.symbolic_solver import SymbolicSolver

async def test_pipeline():
    print("--- Testing Math Normalizer ---")
    normalizer = MathQueryNormalizer()
    
    queries = [
        "what is the derivative of tan(x)?",
        "integrate x^2",
        "solve 2*x + 5 = 15",
        "calculate 5 + 3 * 2"
    ]
    
    intents = []
    
    for q in queries:
        intent = normalizer.normalize(q)
        print(f"Query: '{q}'")
        if intent:
            print(f"  -> Intent: {intent.intent}, Expression: '{intent.expression}'")
            intents.append(intent)
        else:
            print("  -> NO INTENT DETECTED")
            
    print("\n--- Testing Symbolic Solver (SymPy fallback) ---")
    solver = SymbolicSolver() 
    
    for intent in intents:
        print(f"Solving: {intent.intent} -> {intent.expression}")
        res = solver.solve(intent)
        print(f"  Result: {res}")
    
if __name__ == "__main__":
    asyncio.run(test_pipeline())
