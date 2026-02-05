import json
import logging
import os
import re
import base64
import asyncio
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

from google import genai
from google.genai import types
import pybreaker
from tenacity import retry, stop_after_attempt, wait_random_exponential, retry_if_exception_type
from app.core.settings import settings

# Configure logging
logger = logging.getLogger(__name__)

class GeminiSolver:
    """
    Wrapper for the Gemini API using the new google-genai SDK (v1.0+).
    Enforces structured output, cleans unicode, and handles retries/timeouts.
    """

    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-2.5-flash"):
        """
        Initialize the GeminiSolver.

        Args:
            api_key: Gemini API key. Defaults to settings.GOOGLE_API_KEY.
            model_name: Model to use. Defaults to gemini-flash-latest.
        """
        self.api_key = api_key or settings.GOOGLE_API_KEY
        if not self.api_key:
            logger.warning("No API key provided for GeminiSolver. Calls will fail.")
        
        self.client = genai.Client(api_key=self.api_key)
        self.model_name = model_name
        
        # Initialize Circuit Breaker
        # Trips after 5 consecutive failures, resets after 60 seconds
        self.breaker = pybreaker.CircuitBreaker(
            fail_max=5, 
            reset_timeout=60,
            listeners=[pybreaker.CircuitBreakerListener()] # Optional: add listeners for logging
        )

    def _clean_text(self, text: str) -> str:
        """
        Sanitizes text by removing spaced letters and normalizing unicode math to ASCII/LaTeX.
        """
        if not isinstance(text, str):
            return text
            
        # remove accidental spaced letters like 'f ( x )' -> 'f(x)' mostly handled by regex logic provided
        # The user provided: re.sub(r'(?<=\b\w) (?=\w\b)', '', text)
        # We will use that.
        text = re.sub(r'(?<=\b\w) (?=\w\b)', '', text)
        
        # normalize unicode math
        replacements = {
            "−": "-",
            "∞": "\\infty",
            "𝑓": "f",
            "𝑠": "s",
            "𝑡": "t",
            "𝐿": "L",
            "𝐹": "F",
            "𝑒": "e",
            "∫": "\\int",
            "∂": "\\partial",
            "∑": "\\sum",
            "∏": "\\prod",
            "√": "\\sqrt",
            # Add more as needed, but this covers the user's example
        }
        for k, v in replacements.items():
            text = text.replace(k, v)
        return text

    def _safe_parse_json(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Attempts to parse JSON safely, with fallback to regex extraction.
        """
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Fallback: try extracting JSON object from text (e.g., if wrapped in markdown code blocks)
            # Look for the first outer-most curly braces
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
            return None

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_random_exponential(multiplier=1, max=60),
        retry=retry_if_exception_type(Exception),
        reraise=True
    )
    async def solve(self, problem_text: str, image_data: Optional[str] = None, model_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Solves a math problem using Gemini with timeout protection.
        Args:
            problem_text: The text prompt/context.
            image_data: Optional Base64 encoded image string (without prefix).
            model_name: Optional override for the model to use.
        """
        return await self.breaker.call(
            self._solve_with_timeout,
            problem_text,
            image_data,
            model_name,
            timeout=60  # seconds
        )

    async def _solve_with_timeout(self, problem_text: str, image_data: Optional[str] = None, model_name: Optional[str] = None, timeout: int = 60) -> Dict[str, Any]:
        """Solve with timeout enforcement."""
        try:
            # Wrap in timeout context
            result = await asyncio.wait_for(
                asyncio.to_thread(self._solve_internal, problem_text, image_data, model_name),
                timeout=timeout
            )
            return result
        except asyncio.TimeoutError:
            raise TimeoutError(f"Gemini API did not respond within {timeout}s")

    def _solve_internal(self, problem_text: str, image_data: Optional[str] = None, model_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Solves a math problem using Gemini, requesting structured JSON output.

        Args:
            problem_text: The math problem text.
            image_data: Optional Base64 image data.
            model_name: Optional override model.

        Returns:
            Dict[str, Any]: Structured solution containing latex, reasoning, answer, confidence.
        """
        if not problem_text and not image_data:
             raise ValueError("Input cannot be empty.")
        
        # Use provided model or default
        target_model = model_name or self.model_name

        prompt = f"""
        You are a high-efficiency multimodal math solver. Output strictly valid JSON.
        
        Strategy: "Think Aloud -> Extract -> Solve -> Verify -> Box Answer"
        
        Format:
        {{
            "latex": "The exact problem statement in LaTeX",
            "reasoning": "Step-by-step logical derivation. Use standard sentences. Wrap formulas in $...$. Explain identifying the problem type (e.g. Geometry, Algebra).",
            "final_answer": "The bare result (boxed in LaTeX)",
            "confidence_score": 0.0-1.0
        }}

        STRICT FORMATTING RULES:
        - Use ASCII characters only.
        - Use LaTeX for formulas.
        - Wrap all formulas in $...$ or $$...$$
        - Do NOT use unicode math symbols.
        - Do NOT split words with spaces.
        - Do NOT insert newlines inside formulas.
        
        VISUAL REASONING (if image provided):
        1. Extract all visible text, numbers, and geometric labels.
        2. Identify the type of problem (Handwritten Equation, Geometry Diagram, Chart/Plot).
        3. If it's a Chart/Plot, explicitly list extracted data points before solving.
        4. If it's Handwritten, transcribe carefully.

        Problem Context:
        {problem_text}
        """
        
        # Prepare contents
        contents = [prompt]
        
        if image_data:
            try:
                # Decode base64 to bytes
                image_bytes = base64.b64decode(image_data)
                # Ensure we handle common image formats, defaulting to png if unknown/generic
                # Ideally we pass mime_type, but 'image/png' works for most or we can detect.
                # Since InputProcessor handles headers, we assume valid image bytes.
                # types.Part maps to the SDK's Part object
                image_part = types.Part.from_bytes(data=image_bytes, mime_type="image/png")
                contents.append(image_part)
            except Exception as e:
                logger.warning(f"Failed to process image attachment: {e}")
                # Put a note in prompt instead
                contents[0] += "\n[Error: Image attachment failed to load, rely on text]"

        try:
            # New SDK usage
            response = self.client.models.generate_content(
                model=target_model,
                contents=contents,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.2
                )
            )
            
            raw_text = response.text
            if not raw_text:
                raise ValueError("Empty response from Gemini API")

            # Parse JSON safely
            result = self._safe_parse_json(raw_text)
            
            if result is None:
                # Raise error to trigger retry (or capture raw response in caller)
                raise ValueError(f"Failed to parse JSON from response: {raw_text[:200]}...")

            # Apply Sanitization
            for k in result:
                if isinstance(result[k], str):
                    result[k] = self._clean_text(result[k])

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
