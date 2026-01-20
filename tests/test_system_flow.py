import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Add app to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.orchestrator import Orchestrator
from app.core.input_processor import InputType

class TestSystemFlow(unittest.TestCase):
    def setUp(self):
        # Patch external dependencies BEFORE initializing Orchestrator
        self.gemini_patcher = patch('app.core.orchestrator.GeminiSolver')
        self.db_patcher = patch('app.core.orchestrator.DatabaseManager')
        self.cache_patcher = patch('app.core.orchestrator.CacheManager')

        self.MockGemini = self.gemini_patcher.start()
        self.MockDB = self.db_patcher.start()
        self.MockCache = self.cache_patcher.start()

        # Setup Mock Instances
        self.mock_solver = self.MockGemini.return_value
        self.mock_db = self.MockDB.return_value
        self.mock_cache = self.MockCache.return_value

        self.orchestrator = Orchestrator()

    def tearDown(self):
        self.gemini_patcher.stop()
        self.db_patcher.stop()
        self.cache_patcher.stop()

    def test_full_flow_success(self):
        """Test the compelte flow: Input -> Miss Cache -> Solve -> Save -> Return"""
        
        # 1. Setup Data
        user_input = "Solve 2x + 4 = 10"
        mock_solution = {
            "latex": "2x + 4 = 10",
            "reasoning": "2x = 6, x = 3",
            "final_answer": "x = 3",
            "confidence_score": 0.95
        }
        
        # 2. Configure Mocks
        self.mock_cache.get_cached_answer.return_value = None # Cache Miss
        self.mock_db.find_by_hash.return_value = None         # DB Miss
        self.mock_solver.solve.return_value = mock_solution   # Solver Success
        
        # 3. Execution
        result = self.orchestrator.process_problem(user_input)

        # 4. Assertions
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["answer"], mock_solution)
        self.assertEqual(result["metadata"]["source"], "generated")
        
        # Verify calls
        self.mock_cache.get_cached_answer.assert_called_once()
        self.mock_db.find_by_hash.assert_called_once()
        self.mock_solver.solve.assert_called_once_with("solve 2x + 4 = 10") # Input is normalized
        self.mock_db.save_problem.assert_called_once()
        self.mock_cache.set_cached_answer.assert_called_once()

    def test_cache_hit(self):
        """Test flow when answer is in cache."""
        user_input = "What is 2+2?"
        cached_answer = {
            "latex": "2+2",
            "reasoning": "Simple addition",
            "final_answer": "4",
            "confidence_score": 1.0
        }

        self.mock_cache.get_cached_answer.return_value = cached_answer

        result = self.orchestrator.process_problem(user_input)

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["answer"], cached_answer)
        self.assertEqual(result["metadata"]["source"], "cache")
        
        # Verify NO solve calls
        self.mock_solver.solve.assert_not_called()
        self.mock_db.save_problem.assert_not_called()

    def test_invalid_input(self):
        """Test flow with invalid input."""
        user_input = "" # Empty input

        result = self.orchestrator.process_problem(user_input)

        self.assertEqual(result["status"], "error")
        # Depending on input processor, it should return an error
        self.assertIsNotNone(result["error"])
        
        self.mock_solver.solve.assert_not_called()

if __name__ == '__main__':
    unittest.main()
