import logging
import json
import re
import asyncio
from typing import Any, Dict, Optional
import ollama
from app.models.base import BaseModel

logger = logging.getLogger(__name__)

class QwenModel(BaseModel):
    """
    Wrapper for a local Qwen model via Ollama.
    optimized for simple text-based internal reasoning/math.
    """

    def __init__(self, model_name: str = "qwen2.5:3b"):
        """
        Args:
            model_name: The name of the model in Ollama (e.g., 'qwen2.5:7b', 'qwen2.5-math').
        """
        self.model_name = model_name

    async def solve(self, prompt: str, image_data: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """
        Solves using local Qwen. 
        Note: Qwen 2.5 Math is text-only usually, unless using VL version.
        We will reject images for now as per plan.
        """
        if image_data:
             logger.warning("QwenModel received image data, but ignoring it (text-only fallback).")

        full_prompt = f"""
        You are a helpful math assistant. Solve this problem carefully.
        Return ONLY valid JSON.
        
        Strategy: "Think Aloud -> Extract -> Solve -> Verify -> Box Answer"

        Format:
        {{
            "latex": "The exact problem statement in LaTeX",
            "reasoning": "Step-by-step logical derivation. Use standard sentences. Wrap formulas in $...$.",
            "final_answer": "The bare result (boxed in \\boxed{{...}})",
            "confidence_score": 0.0-1.0
        }}
        
        STRICT FORMATTING RULES:
        - Use ASCII characters only.
        - Use LaTeX for formulas.
        - Wrap all formulas in $...$ or $$...$$
        - Do NOT use unicode math symbols.
        
        Problem: {prompt}
        """

        try:
            # Run blocking inference in a thread
            response = await asyncio.to_thread(
                ollama.chat,
                model=self.model_name,
                messages=[{'role': 'user', 'content': full_prompt}],
                format='json'
            )
            
            content = response['message']['content']
            
            # Parse JSON
            try:
                result = json.loads(content)
            except json.JSONDecodeError:
                logger.error(f"Failed to parse Qwen JSON: {content}")
                 # Fallback manual extraction could go here
                return {
                    "answer": content,
                    "confidence": 0.5,
                    "model": "qwen",
                    "error": "json_parse_error"
                }

            # Normalize keys to match system expectation
            if "answer" not in result and "final_answer" in result:
                result["answer"] = result["final_answer"]
            
            if "confidence" not in result:
                result["confidence"] = result.get("confidence_score", 0.6)
                
            result["model"] = "qwen"
            return result

        except Exception as e:
            logger.error(f"Qwen/Ollama inference failed: {e}")
            raise e
