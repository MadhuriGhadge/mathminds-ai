import json
import logging
import os
import re
from typing import Any, Dict, Optional

from google import genai
from google.genai import types
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# Configure logging
logger = logging.getLogger(__name__)

class GeminiSolver:
    """
    Wrapper for the Gemini API using the new google-genai SDK (v1.0+).
    Enforces structured output, cleans unicode, and handles retries/timeouts.
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
            "reasoning": "Explain clearly using normal sentences. Use LaTeX formulas wrapped in $...$.",
            "final_answer": "The bare result",
            "confidence_score": 0.0-1.0
        }}

        STRICT FORMATTING RULES:
        - Use ASCII characters only.
        - Use LaTeX for formulas.
        - Wrap all formulas in $...$ or $$...$$
        - Do NOT use unicode math symbols.
        - Do NOT split words with spaces.
        - Do NOT insert newlines inside formulas.

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
