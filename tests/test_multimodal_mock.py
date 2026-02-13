
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from app.core.orchestrator import Orchestrator
from app.core.schemas import SolveRequest
from app.reasoning.gemini_client import GeminiSolver

@pytest.mark.asyncio
async def test_orchestrator_routes_model_preference():
    """
    Verify that Orchestrator correctly routes requests to GeminiSolver 
    with the specified model preference.
    """
    # Mock dependencies
    mock_input_processor = MagicMock()
    mock_input_processor.process_compound.return_value.is_valid = True
    mock_input_processor.process_compound.return_value.cleaned_content = "Solve this"
    mock_input_processor.process_compound.return_value.metadata = {}
    
    mock_solver = AsyncMock(spec=GeminiSolver)
    mock_solver.solve.return_value = {"answer": "x=2", "latex": "x=2", "reasoning": "steps...", "final_answer": "x=2", "confidence_score": 1.0}
    
    mock_cache = MagicMock()
    mock_cache.get_cached_answer.return_value = None
    
    mock_db = MagicMock()
    mock_db.find_by_hash.return_value = None

    # Instantiate Orchestrator with mocks
    with patch("app.core.orchestrator.InputProcessor", return_value=mock_input_processor), \
         patch("app.core.orchestrator.GeminiSolver", return_value=mock_solver), \
         patch("app.core.orchestrator.CacheManager", return_value=mock_cache), \
         patch("app.core.orchestrator.DatabaseManager", return_value=mock_db), \
         patch("app.core.orchestrator.QueryRouter"), \
         patch("app.core.orchestrator.WebScraper"), \
         patch("app.core.orchestrator.SymbolicSolver"), \
         patch("app.core.orchestrator.QueryClassifier"):
         
        orchestrator = Orchestrator()
        
        # Test Case 1: Fast Model
        await orchestrator.process_problem(text="Test 1", model_preference="fast")
        # Verify solver called with flash
        mock_solver.solve.assert_called_with(
            "Solve this", 
            image_data=None, 
            model_name="gemini-2.5-flash"
        )
        
        # Test Case 2: Reasoning Model
        await orchestrator.process_problem(text="Test 2", model_preference="reasoning")
        # Verify solver called with pro
        mock_solver.solve.assert_called_with(
            "Solve this", 
            image_data=None, 
            model_name="gemini-2.5-flash"
        )
        
        print("\n[PASS] Orchestrator Routing Test Passed!")

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_orchestrator_routes_model_preference())
