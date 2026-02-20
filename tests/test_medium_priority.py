
import pytest
from unittest.mock import MagicMock, patch
import os
from app.api.main import app
from app.core.settings import settings
from app.tools.vision_analyzer import VisionAnalyzer
from app.core.orchestrator import Orchestrator

def test_settings_validation():
    assert hasattr(settings, "MAX_LLM_CALLS_PER_DAY")
    assert isinstance(settings.MAX_LLM_CALLS_PER_DAY, int)

def test_yolo_lazy_loading():
    analyzer = VisionAnalyzer()
    assert analyzer.model is None
    # We won't test _ensure_model to avoid downloading weights during test

@pytest.mark.asyncio
async def test_quota_persistence_prevention():
    # Mock dependencies
    mock_db = MagicMock()
    mock_agent = MagicMock()
    mock_agent.solve.return_value = "⚠️ Daily limit reached (18/18). Please try again tomorrow."
    
    orchestrator = Orchestrator(db_manager=mock_db)
    orchestrator.adk_agent = mock_agent
    
    # Mock input processing
    with patch("app.core.input_processor.InputProcessor.process") as mock_process:
        mock_process.return_value.cleaned_content = "test"
        
        # Execute
        result = await orchestrator.process_problem("test", user_id="test_user")
        
        # Verify DB save was skipped
        mock_db.save_problem.assert_not_called()
        assert result["status"] == "success" # It returns success but isn't saved
