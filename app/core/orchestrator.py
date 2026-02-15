
import logging
import time
from typing import Any, Dict, Optional

from app.core.input_processor import InputProcessor
from app.memory.cache import CacheManager
from app.memory.database import DatabaseManager
from app.agents.adk_mathminds import MathMindsADKAgent
from app.core.settings import settings

logger = logging.getLogger(__name__)

class Orchestrator:
    """
    Simplified Orchestrator for MathMinds AI (Pure ADK Architecture).
    Delegates all reasoning and tool usage to the MathMindsADKAgent.
    """

    def __init__(self, cache_manager: Optional[CacheManager] = None, db_manager: Optional[DatabaseManager] = None):
        try:
            self.input_processor = InputProcessor()
            self.cache_manager = cache_manager or CacheManager()
            self.db_manager = db_manager or DatabaseManager()
            
            # The Single Source of Truth
            self.adk_agent = MathMindsADKAgent()
            
        except Exception as e:
            logger.critical(f"Failed to initialize Orchestrator: {e}")
            raise

    async def process_problem(self, text: Optional[str] = None, image: Optional[str] = None, request_id: Optional[str] = None, model_preference: str = "fast", session_id: Optional[str] = None, user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Streamlined Pipeline: Input -> Agent -> Output.
        """
        start_time = time.time()
        request_id = request_id or "unknown"
        
        # Default Schema
        result_schema = {
            "request_id": request_id,
            "status": "error",
            "source": "google_adk_agent",
            "answer": None,
            "steps": [],
            "explanation": None,
            "confidence": 0.0,
            "cached": False,
            "metadata": {
                "latency_ms": 0,
                "model": "gemini-flash-adk",
                "tools_used": []
            }
        }

        try:
            # 1. Input Processing
            processed = self.input_processor.process_compound(text_input=text, image_input=image)
            if not processed.is_valid:
                result_schema["explanation"] = processed.error_message
                return self._finalize_result(result_schema, start_time)

            # 2. Agent Execution
            logger.info("Routing request to ADK Agent")
            
            # Pass image data if available
            image_data_b64 = processed.metadata.get("image_data")
            
            try:
                agent_response = await self.adk_agent.solve(
                    problem=processed.cleaned_content,
                    image_data=image_data_b64,
                    session_id=session_id or "default_session",
                    user_id=user_id or "default_user"
                )
                
                result_schema["status"] = "success"
                result_schema["answer"] = agent_response
                result_schema["explanation"] = "Processed by MathMinds ADK Agent."
                result_schema["confidence"] = 1.0 
                
            except Exception as e:
                logger.error(f"ADK Agent execution failed: {e}")
                result_schema["explanation"] = f"Agent Error: {str(e)}"
                return self._finalize_result(result_schema, start_time)

            # 3. Persistence (Cache & DB)
            if result_schema["status"] == "success":
                if settings.ENABLE_CACHE:
                     # Simple hash for caching (content + image)
                     # Note: In a real agent scenario, caching entire conversations is complex.
                     # We skip aggressive caching for now to rely on Agent's session memory,
                     # or we cache only exact single-turn queries if needed.
                     pass 

                # Save to DB for history
                self.db_manager.save_problem(
                    {"content": processed.cleaned_content}, 
                    result_schema
                )

            return self._finalize_result(result_schema, start_time)

        except Exception as e:
            logger.error(f"Orchestrator Critical Error: {e}")
            result_schema["explanation"] = f"Internal Error: {str(e)}"
            return self._finalize_result(result_schema, start_time)

    def _finalize_result(self, schema: Dict, start_time: float) -> Dict:
        """Calculates latency and returns final dict."""
        schema["metadata"]["latency_ms"] = int((time.time() - start_time) * 1000)
        return schema
