import sys
import os
import asyncio
from unittest.mock import MagicMock

sys.path.append(os.getcwd())

# Mock modules BEFORE importing Orchestrator
sys.modules['app.models.gemini'] = MagicMock()
sys.modules['app.models.qwen'] = MagicMock()
sys.modules['app.tools.vision_analyzer'] = MagicMock() # Mock entire module

# Mocking VisionAnalyzer class specifically in the module mock
mock_vision_module = sys.modules['app.tools.vision_analyzer']
mock_vision_module.VisionAnalyzer = MagicMock()

from app.core.orchestrator import Orchestrator

async def verify():
    print("Initializing Orchestrator with mocks...")
    
    # Mock dependencies
    mock_cache = MagicMock()
    mock_cache.get_cached_answer.return_value = None # Force cache MISS
    mock_db = MagicMock()
    
    # We need real logic for Orchestrator, but mocks for heavy lifting
    orch = Orchestrator(cache_manager=mock_cache, db_manager=mock_db)
    
    # Ensure symbolic solver is real (it should be, unless we mocked app.tools.symbolic_solver)
    # math_normalizer should be real too.
    
    query = "derivative of tan(x)"
    print(f"\nProcessing query: '{query}'")
    
    # We need to mock InputProcessor's return value to bypass complexity there
    # But we want the text to flow through
    mock_processed = MagicMock()
    mock_processed.is_valid = True
    mock_processed.cleaned_content = query
    mock_processed.metadata = {}
    mock_processed.input_type.value = "text"
    
    orch.input_processor.process_compound = MagicMock(return_value=mock_processed)
    
    # Run
    # Note: we pass text=query but input_processor mock will control what's used
    result = await orch.process_problem(text=query)
    
    print("\nOrchestrator Result Status:", result.get("status"))
    
    if result.get("status") == "success":
        ans = result.get("answer", {})
        print("Answer Keys:", list(ans.keys()))
        
        required = ["final_answer", "latex", "confidence_score", "reasoning"]
        missing = [k for k in required if k not in ans]
        
        if not missing:
            print("✅ SUCCESS: All required keys present.")
            print(f"   Final Answer: {ans['final_answer']}")
        else:
            print(f"❌ FAIL: Missing keys: {missing}")
            print(f"   Actual Answer Dict: {ans}")
            
    else:
        print(f"❌ FAIL: Process failed with error: {result.get('error_msg')}")
        print(f"   Debug: {result.get('metadata', {}).get('debug_error')}")

if __name__ == "__main__":
    asyncio.run(verify())
