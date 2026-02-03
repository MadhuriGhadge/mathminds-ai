
import unittest
import json
import logging
import uuid
# Mock components
from unittest.mock import MagicMock, patch

from app.reasoning.gemini_client import GeminiSolver
from app.core.orchestrator import Orchestrator
from app.api.deps import get_orchestrator

class TestReliability(unittest.TestCase):

    def setUp(self):
        logging.basicConfig(level=logging.ERROR)

    def test_safe_parse_json(self):
        """Test the JSON repair logic in GeminiSolver."""
        solver = GeminiSolver(api_key="fake")
        
        # Test 1: Valid JSON
        valid = '{"key": "value"}'
        self.assertEqual(solver._safe_parse_json(valid), {"key": "value"})
        
        # Test 2: Wrapped in markdown
        wrapped = '```json\n{"key": "value"}\n```'
        self.assertEqual(solver._safe_parse_json(wrapped), {"key": "value"})
        
        # Test 3: Surrounded by text
        surrounded = 'Here is the json: {"key": "value"} thanks.'
        self.assertEqual(solver._safe_parse_json(surrounded), {"key": "value"})
        
        # Test 4: Invalid JSON
        invalid = '{key: value}' # Missing quotes
        self.assertIsNone(solver._safe_parse_json(invalid))

    @patch("app.core.orchestrator.GeminiSolver")
    @patch("app.core.orchestrator.CacheManager")
    @patch("app.core.orchestrator.DatabaseManager")
    def test_orchestrator_error_metadata(self, mock_db, mock_cache, mock_solver):
        """Test that Orchestrator returns rich error metadata."""
        
        # Setup mocks
        mock_solver_inst = mock_solver.return_value
        mock_solver_inst.solve.side_effect = Exception("Failed to parse JSON")
        
        # Ensure cache miss
        mock_cache.return_value.get_cached_answer.return_value = None
        mock_db.return_value.find_by_hash.return_value = None
        
        orchestrator = Orchestrator()
        
        # Call process_problem
        req_id = "test-uuid-123"
        result = orchestrator.process_problem("test input", request_id=req_id)
        
        # Verify structure
        self.assertEqual(result["status"], "error")
        self.assertIn("metadata", result)
        self.assertEqual(result["metadata"]["request_id"], req_id)
        self.assertEqual(result["metadata"]["stage"], "reasoning")
        self.assertIn("error_detail", result["metadata"])
        
    def test_dependency_injection(self):
        """Test that the dependency provider works."""
        orch = get_orchestrator()
        self.assertIsInstance(orch, Orchestrator)
        
        # Verify singleton behavior (lru_cache)
        orch2 = get_orchestrator()
        self.assertIs(orch, orch2)

if __name__ == "__main__":
    unittest.main()
