
import pytest
from unittest.mock import MagicMock, patch
import os
from app.core.orchestrator import Orchestrator
from app.core.settings import settings
import gunicorn_conf

def test_confidence_scoring():
    orchestrator = Orchestrator(db_manager=MagicMock())
    
    # Test high confidence
    score_high = orchestrator._calculate_confidence("The derivative of x^2 is 2x.")
    assert score_high == 1.0
    
    # Test hedging
    score_low = orchestrator._calculate_confidence("I think the answer might be 42 but not sure.")
    assert score_low == 0.7
    
    # Test empty
    assert orchestrator._calculate_confidence("") == 0.0

@pytest.mark.asyncio
async def test_caching_flow():
    # Mock settings to ensure cache is enabled
    settings.ENABLE_CACHE = True
    
    mock_cache = MagicMock()
    mock_db = MagicMock()
    
    # 1. Test Cache Hit
    orchestrator = Orchestrator(cache_manager=mock_cache, db_manager=mock_db)
    
    # Setup mock to return cached answer
    cached_payload = {
        "status": "success", 
        "answer": "cached answer", 
        "cached": True, 
        "metadata": {}
    }
    mock_cache.get_cached_answer.return_value = cached_payload
    
    # Mock input processing
    with patch("app.core.input_processor.InputProcessor.process_compound") as mock_input:
        mock_input.return_value.is_valid = True
        mock_input.return_value.cleaned_content = "test query"
        mock_input.return_value.metadata = {}
        
        result = await orchestrator.process_problem(text="test query")
        
        assert result["answer"] == "cached answer"
        assert result["cached"] is True
        # Agent should NOT be called if cache hit (we didn't mock adk_agent here so if called it would crash or fail)

    # 2. Test Cache Miss & Write
    mock_cache.get_cached_answer.return_value = None
    mock_agent = MagicMock()
    mock_agent.solve.return_value = "fresh answer"
    orchestrator.adk_agent = mock_agent
    
    with patch("app.core.input_processor.InputProcessor.process_compound") as mock_input:
        mock_input.return_value.is_valid = True
        mock_input.return_value.cleaned_content = "fresh query"
        mock_input.return_value.metadata = {}
        
        result_fresh = await orchestrator.process_problem(text="fresh query")
        
        assert result_fresh["answer"] == "fresh answer"
        # Verify set_cached_answer was called
        mock_cache.set_cached_answer.assert_called_once()

def test_gunicorn_timeout():
    assert gunicorn_conf.timeout == 360
