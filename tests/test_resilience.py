import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pybreaker
from app.core.orchestrator import Orchestrator
from app.reasoning.gemini_client import GeminiSolver
from app.memory.cache import CacheManager
from app.memory.database import DatabaseManager

class TestResilience(unittest.TestCase):
    
    def test_cache_failure_fallback(self):
        """Test that Orchestrator falls back to DB when Cache fails."""
        # Setup
        mock_cache = MagicMock(spec=CacheManager)
        mock_cache.get_cached_answer.side_effect = Exception("Redis Down")
        
        mock_db = MagicMock(spec=DatabaseManager)
        mock_db.find_by_hash.return_value = {"answer": {"final_answer": "42"}} # Mock DB Hit
        
        orchestrator = Orchestrator(cache_manager=mock_cache, db_manager=mock_db)
        
        # Action
        result = orchestrator.process_problem("What is 6*7?")
        
        # Assert
        self.assertEqual(result["answer"]["final_answer"], "42")
        self.assertEqual(result["metadata"]["source"], "database")
        print("PASS: Cache failure correctly fell back to DB.")

    def test_db_failure_fallback(self):
        """Test that Orchestrator falls back to Solver when DB fails."""
        # Setup
        mock_cache = MagicMock(spec=CacheManager)
        mock_cache.get_cached_answer.return_value = None # Cache miss
        
        mock_db = MagicMock(spec=DatabaseManager)
        mock_db.find_by_hash.side_effect = Exception("DB Down")
        
        orchestrator = Orchestrator(cache_manager=mock_cache, db_manager=mock_db)
        # Mock the solver to avoid real API calls
        orchestrator.solver = MagicMock()
        orchestrator.solver.solve.return_value = {
            "final_answer": "42",
            "latex": "6 \\times 7",
            "reasoning": "Standard multiplication",
            "confidence_score": 1.0
        }
        
        # Action
        result = orchestrator.process_problem("What is 6*7?")
        
        # Assert
        self.assertEqual(result["answer"]["final_answer"], "42")
        self.assertEqual(result["metadata"]["source"], "generated")
        print("PASS: DB failure correctly fell back to Solver.")

    def test_circuit_breaker(self):
        """Test that Circuit Breaker opens after max failures."""
        solver = GeminiSolver(api_key="fake")
        # Ensure breaker is closed initially
        solver.breaker.close()
        
        # Mock internal solve to always fail
        solver._solve_internal = MagicMock(side_effect=Exception("API Error"))
        
        # We need to bypass the @retry decorator for this unit test to test the breaker specifically,
        # otherwise we wait for retries. Ideally we test integration, but unit test is faster for verification.
        # Alternatively, we just call solve() 6 times. The separate @retry might slow it down, 
        # so we can mock the checking logic or just reduce retry counts for test.
        # Actually, pybreaker wraps the call. We can just call breaker.call directly on a failing func.
        
        print("Simulating 5 failures...")
        for i in range(5):
            try:
                # We call the breaker directly to test IT, skipping the retry wrapper for speed
                solver.breaker.call(solver._solve_internal, "problem")
            except Exception:
                pass
        
        # 6th call should raise CircuitBreakerError
        print("Simulating 6th failure (Expect CircuitBreakerError)...")
        with self.assertRaises(pybreaker.CircuitBreakerError):
            solver.breaker.call(solver._solve_internal, "problem")
            
        print("PASS: Circuit breaker opened after 5 failures.")

if __name__ == '__main__':
    unittest.main()
