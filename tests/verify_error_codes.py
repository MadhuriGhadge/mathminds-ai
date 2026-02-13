import sys
import os
import unittest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.api.main import app
from app.api.deps import get_orchestrator
from app.core.errors import ErrorCodes, ERROR_MESSAGES

class TestErrorSanitization(unittest.TestCase):
    def setUp(self):
        self.mock_orchestrator = MagicMock()
        app.dependency_overrides[get_orchestrator] = lambda: self.mock_orchestrator
        self.client = TestClient(app)

    def test_sanitized_error_response(self):
        # Simulate Orchestrator returning an error with internal debug info
        error_result = {
            "status": "error",
            "answer": None,
            "error_code": ErrorCodes.INPUT_VALIDATION_ERROR,
            "error_msg": ERROR_MESSAGES[ErrorCodes.INPUT_VALIDATION_ERROR],
            "metadata": {
                "request_id": "test-req-id",
                "stage": "input_processing",
                "_internal_debug": "Stack trace: ... sensitive info ..."
            }
        }
        self.mock_orchestrator.process_problem.return_value = error_result

        response = self.client.post("/solve", json={"input": "bad input"})
        
        # Assertions
        self.assertEqual(response.status_code, 200) # We return 200 with status=error in body usually, or 400? 
        # Wait, main.py returns SolveResponse which is usually 200 unless exception raised.
        # My implementation of process_problem returns a dict, main.py returns SolveResponse.
        
        data = response.json()
        print(f"\nResponse Body: {data}")
        
        self.assertEqual(data["status"], "error")
        self.assertEqual(data["error_code"], "ERR_002") # INPUT_VALIDATION_ERROR
        self.assertEqual(data["error"], "The input provided is invalid.")
        
        # CRITICAL: Check sanitization
        self.assertIn("metadata", data)
        self.assertNotIn("_internal_debug", data["metadata"])
        self.assertIn("request_id", data["metadata"])

    def tearDown(self):
        app.dependency_overrides = {}

if __name__ == '__main__':
    unittest.main()
