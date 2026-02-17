import pytest
import asyncio
from fastapi.testclient import TestClient
from app.api.main import app
from unittest.mock import MagicMock, patch
from app.core.security import get_current_user

# Mock Auth
app.dependency_overrides[get_current_user] = lambda: {"uid": "test_mid", "email": "test@test.com"}

client = TestClient(app)

# Mock the orchestrator to avoid initializing real heavy models
@pytest.fixture
def mock_orchestrator():
    with patch("app.api.deps.get_orchestrator") as mock:
        mock_instance = MagicMock()
        
        async def mock_process(*args, **kwargs):
            return {
                "status": "success",
                "answer": "Mocked Answer",
                "metadata": {"request_id": kwargs.get("request_id")},
                "steps": [],
                "explanation": "Mocked",
                "confidence": 1.0,
                "cached": False,
                "source": "mock"
            }
            
        mock_instance.process_problem = mock_process
        mock.return_value = mock_instance
        yield mock_instance

def test_deduplication(mock_orchestrator):
    """
    Test that sending the same request_id twice results in 409 for the second one.
    """
    req_id = "test-dedup-uuid-1234"
    payload = {
        "text": "1+1",
        "request_id": req_id,
        "model_preference": "fast"
    }

    # Simulate concurrent requests with same ID is hard with TestClient (sync).
    # But we can try to fire them or just rely on the fact that if we use proper async test client it works.
    # Standard TestClient is sync.
    
    # Actually, to test "active_requests", we need the first request to be SLOW.
    # Let's mock orchestrator to sleep.
    
    async def slow_process(*args, **kwargs):
        await asyncio.sleep(0.5)
        return {
            "status": "success", 
            "answer": "Slow Answer", 
            "metadata": {"request_id": kwargs.get("request_id")},
            "status": "success"
        }
    
    with patch("app.core.orchestrator.Orchestrator.process_problem", side_effect=slow_process) as mock_process:
        # We need async client for concurrency
        from httpx import AsyncClient, ASGITransport
        
        async def run_concurrent():
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                task1 = asyncio.create_task(ac.post("/solve", json=payload))
                task2 = asyncio.create_task(ac.post("/solve", json=payload))
                
                responses = await asyncio.gather(task1, task2)
                return responses

        responses = asyncio.run(run_concurrent())
        
        status_codes = [r.status_code for r in responses]
        assert 409 in status_codes
        assert 200 in status_codes

if __name__ == "__main__":
    # Manually run if pytest not available
    # But we need to install httpx if not present.
    pass
