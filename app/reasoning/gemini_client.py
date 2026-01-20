import json
import logging
import os
from typing import Any, Dict, Optional

from google import genai
from google.genai import types
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# Configure logging
logger = logging.getLogger(__name__)

class GeminiSolver:
    """
    Wrapper for the Gemini API using the new google-genai SDK (v1.0+).
    Enforces structured output and handles retries/timeouts.
    """

    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-flash-latest"):
        """
        Initialize the GeminiSolver.

        Args:
            api_key: Gemini API key. Defaults to GOOGLE_API_KEY env var.
            model_name: Model to use. Defaults to gemini-flash-latest.
        """
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            logger.warning("No API key provided for GeminiSolver. Calls will fail.")
        
        self.client = genai.Client(api_key=self.api_key)
        self.model_name = model_name

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception),
        reraise=True
    )
    def solve(self, problem_text: str) -> Dict[str, Any]:
        """
        Solves a math problem using Gemini, requesting structured JSON output.

        Args:
            problem_text: The math problem text.

        Returns:
            Dict[str, Any]: Structured solution containing latex, reasoning, answer, confidence.
        """
        if not problem_text:
            raise ValueError("Problem text cannot be empty.")

        prompt = f"""
        You are a high-efficiency math solver. Output strictly valid JSON.
        
        Format:
        {{
            "latex": "The problem statement in LaTeX",
            "reasoning": "Step-by-step derivation. Use symbols (⇒, ∴), short variables, and sentence fragments. Minimize tokens.",
            "final_answer": "The bare result",
            "confidence_score": 0.0-1.0
        }}

        Rules:
        1. Use LaTeX for all math expressions.
        2. No verbose explanations or repetition.
        3. No conversational filler ("Here is the solution...").
        4. "reasoning" must be linear and concise.
        5. Output pure JSON only.

        Problem:
        {problem_text}
        """

        try:
            # New SDK usage
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.2
                )
            )
            
            if not response.text:
                raise ValueError("Empty response from Gemini API")

            # Parse JSON
            result = json.loads(response.text)
            
            # Basic validation of keys
            required_keys = ["latex", "reasoning", "final_answer", "confidence_score"]
            for key in required_keys:
                if key not in result:
                    logger.warning(f"Missing key {key} in Gemini response: {result.keys()}")
                    if key == "confidence_score":
                        result[key] = 0.0 # Default fallback
                    else:
                         result[key] = "Error: Missing in response"
            
            return result

        except Exception as e:
            logger.error(f"Gemini API call failed: {e}")
            raise # Let tenacity handle retry
