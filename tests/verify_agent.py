import sys
import os
import asyncio
from unittest.mock import MagicMock, AsyncMock

sys.path.append(os.getcwd())

# Mock generic modules
sys.modules['app.tools.vision_analyzer'] = MagicMock() 
sys.modules['app.tools.web_scraper'] = MagicMock()
sys.modules['app.models.qwen'] = MagicMock()
# Mock ollama entirely to avoid qwen internal import lag if any
sys.modules['ollama'] = MagicMock()

from app.core.orchestrator import Orchestrator

async def verify_agent_loop():
    print("Initializing Orchestrator with mocks...")
    
    # Mock dependencies
    mock_cache = MagicMock()
    mock_cache.get_cached_answer.return_value = None
    mock_db = MagicMock()
    
    orch = Orchestrator(cache_manager=mock_cache, db_manager=mock_db)
    
    # Mock Input Processor to return valid text
    mock_processed = MagicMock()
    mock_processed.is_valid = True
    mock_processed.cleaned_content = "derivative of x^2"
    mock_processed.metadata = {}
    mock_processed.input_type.value = "text"
    orch.input_processor.process_compound = MagicMock(return_value=mock_processed)

    # Mock Gemini
    orch.gemini = MagicMock()
    
    # --- SIMULATE TOOL CALL RESPONSE ---
    # Create a mock response object structure similar to google-genai SDK
    mock_response_1 = MagicMock()
    mock_response_1.text = "I should use the tool."
    
    # Mock Parts & FunctionCall
    mock_info_part = MagicMock()
    
    mock_fc = MagicMock()
    mock_fc.name = "solve_math_symbolically"
    mock_fc.args = {"problem": "derivative of x^2"}
    
    mock_info_part.function_call = mock_fc
    
    # Candidates list
    mock_candidate = MagicMock()
    mock_candidate.content.parts = [mock_info_part]
    mock_response_1.candidates = [mock_candidate]
    
    # set generate_with_tools return val
    orch.gemini.generate_with_tools = AsyncMock(return_value=mock_response_1)
    
    # --- SIMULATE FINAL ANSWER RESPONSE ---
    final_solution = {
        "final_answer": "2x",
        "reasoning": "Power rule",
        "latex": "2x",
        "confidence_score": 1.0
    }
    orch.gemini.solve = AsyncMock(return_value=final_solution)
    
    # --- MOCK TOOL EXECUTION ---
    # We want to see if the orchestrator actually calls the symbolic solver
    # The Orchestrator's internal _get_tools creates closures calling self.symbolic_solver
    orch.symbolic_solver.solve = MagicMock(return_value={"source": "sympy", "content": "2*x", "status": "success"})
    orch.math_normalizer.normalize = MagicMock(return_value=None) # Pass raw str to solver mock
    
    print("\nRunning Agent Loop...")
    result = await orch.process_problem(text="derivative of x^2")
    
    print("\nOrchestrator Result:", result.get("status"))
    
    # Verify calls
    print("\n--- Verification ---")
    
    # 1. Check if Gemini was called with tools
    if orch.gemini.generate_with_tools.called:
        print("✅ Gemini generate_with_tools called.")
    else:
        print("❌ Gemini generate_with_tools NOT called.")
        
    # 2. Check if Tool was executed (SymbolicSolver)
    # The orchestrator should have called solve_math_symbolically -> symbolic_solver.solve
    if orch.symbolic_solver.solve.called:
        print(f"✅ SymbolicSolver called with: {orch.symbolic_solver.solve.call_args}")
    else:
        print("❌ SymbolicSolver NOT called.")
        
    # 3. Check final answer
    if result["answer"] == final_solution:
        print("✅ Final answer matches expected.")
    else:
        print(f"❌ Final answer mismatch: {result['answer']}")

if __name__ == "__main__":
    asyncio.run(verify_agent_loop())
