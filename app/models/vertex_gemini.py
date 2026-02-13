
import logging
from typing import Optional, Dict, Any, List
# vertexai and related imports
# google-cloud-aiplatform is required
try:
    import vertexai
    from vertexai.generative_models import GenerativeModel, Part
    import vertexai.preview.generative_models as generative_models
except ImportError:
    vertexai = None
    GenerativeModel = None

from app.core.settings import settings
from app.models.base import BaseModel

logger = logging.getLogger(__name__)

class VertexGeminiModel(BaseModel):
    """
    Wrapper for Google Vertex AI Gemini API.
    Offers enterprise features, higher quotas, and better monitoring than the standard API.
    """

    def __init__(self, project_id: str = None, location: str = "us-central1", model_name: str = "gemini-2.5-flash"):
        """
        Initialize Vertex AI client.
        """
        if not vertexai:
            logger.error("google-cloud-aiplatform not installed. VertexGeminiModel disabled.")
            self.model = None
            return

        self.project_id = project_id or settings.GOOGLE_CLOUD_PROJECT
        self.location = location
        self.model_name = model_name

        if not self.project_id:
            logger.warning("No Google Cloud Project ID provided. Vertex AI calls may fail.")

        try:
            vertexai.init(project=self.project_id, location=self.location)
            self.model = GenerativeModel(self.model_name)
        except Exception as e:
            logger.error(f"Failed to initialize Vertex AI: {e}")
            self.model = None

    async def solve(self, prompt: str, image_data: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """
        Solve problem using Vertex AI.
        """
        if not self.model:
            return {"error": "Vertex AI not initialized"}

        full_prompt = f"""
        You are an expert math solver using Vertex AI.
        Return strictly valid JSON.
        
        Strategy: "Think Aloud -> Solve -> Verify"

        Format:
        {{
            "latex": "Problem in LaTeX",
            "reasoning": "Step-by-step solution",
            "final_answer": "Boxed answer",
            "confidence_score": 0.0-1.0
        }}
        
        Problem: {prompt}
        """

        generation_config = {
            "max_output_tokens": 2048,
            "temperature": 0.2,
            "top_p": 0.95,
        }

        # Safety settings to block minimal content
        safety_settings = {
            generative_models.HarmCategory.HARM_CATEGORY_HATE_SPEECH: generative_models.HarmBlockThreshold.BLOCK_ONLY_HIGH,
            generative_models.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: generative_models.HarmBlockThreshold.BLOCK_ONLY_HIGH,
            generative_models.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: generative_models.HarmBlockThreshold.BLOCK_ONLY_HIGH,
            generative_models.HarmCategory.HARM_CATEGORY_HARASSMENT: generative_models.HarmBlockThreshold.BLOCK_ONLY_HIGH,
        }

        try:
            # TODO: Handle image_data (convert base64 to Part)
            # For now, text only
            if image_data:
                logger.warning("Image data not fully supported in Vertex wrapper yet.")

            responses = await self.model.generate_content_async(
                [full_prompt],
                generation_config=generation_config,
                safety_settings=safety_settings,
                stream=False,
            )
            
            # Vertex AI response parsing
            text_response = responses.text
            
            # Simple wrapper return - in production, need parsing logic similar to GeminiModel
            return {
                "raw_response": text_response,
                "model": "vertex-gemini",
                "status": "success"
            }

        except Exception as e:
            logger.error(f"Vertex AI generation failed: {e}")
            return {"error": str(e)}
