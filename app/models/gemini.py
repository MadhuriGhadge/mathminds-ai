import json
import logging
import re
import base64
import asyncio
from typing import Any, Dict, Optional

from google import genai
from google.genai import types
import pybreaker
from tenacity import retry, stop_after_attempt, wait_random_exponential, retry_if_exception_type

from app.core.settings import settings
from app.models.base import BaseModel

# Configure logging
logger = logging.getLogger(__name__)

# Global Semaphore to prevent rate limit exhaustion
_GEMINI_LOCK = asyncio.Semaphore(1)

class GeminiModel(BaseModel):
    """
    Wrapper for the Gemini API using the new google-genai SDK (v1.0+).
    Enforces structured output, cleans unicode, and handles retries/timeouts.
    """

    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-2.5-flash"):
        """
        Initialize the GeminiModel.

        Args:
            api_key: Gemini API key. Defaults to settings.GOOGLE_API_KEY.
            model_name: Model to use. Defaults to gemini-flash-latest.
        """
        self.api_key = api_key or settings.GOOGLE_API_KEY
        if not self.api_key:
            logger.warning("No API key provided for GeminiModel. Calls will fail.")
        
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
            
        text = re.sub(r'(?<=\b\w) (?=\w\b)', '', text)
        
        replacements = {
            "−": "-", "∞": "\\infty", "𝑓": "f", "𝑠": "s", "𝑡": "t",
            "𝐿": "L", "𝐹": "F", "𝑒": "e", "∫": "\\int", "∂": "\\partial",
            "∑": "\\sum", "∏": "\\prod", "√": "\\sqrt",
        }
        for k, v in replacements.items():
            text = text.replace(k, v)
        return text

    def _safe_parse_json(self, text: str) -> Optional[Dict[str, Any]]:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
            return None

    # Removed @retry to prevent 429 stampedes
    async def solve(self, prompt: str, image_data: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """
        Solves a math problem using Gemini with timeout protection and concurrency control.
        """
        model_name = kwargs.get("model_name")
        
        # Global Concurrency Lock (One request at a time)
        async with _GEMINI_LOCK:
            return await self.breaker.call(
                self._solve_with_timeout,
                prompt,
                image_data,
                model_name,
                timeout=60
            )

    async def _solve_with_timeout(self, prompt: str, image_data: Optional[str] = None, model_name: Optional[str] = None, timeout: int = 60) -> Dict[str, Any]:
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(self._solve_internal, prompt, image_data, model_name),
                timeout=timeout
            )
            return result
        except asyncio.TimeoutError:
            raise TimeoutError(f"Gemini API did not respond within {timeout}s")

    def _solve_internal(self, prompt: str, image_data: Optional[str] = None, model_name: Optional[str] = None) -> Dict[str, Any]:
        if not prompt and not image_data:
             raise ValueError("Input cannot be empty.")
        
        target_model = model_name or self.model_name
        
        # We wrap the user prompt in our system instruction here
        full_prompt = f"""
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
        
        Problem Context:
        {prompt}
        """

        contents = [full_prompt]
        
        if image_data:
            try:
                image_bytes = base64.b64decode(image_data)
                image_part = types.Part.from_bytes(data=image_bytes, mime_type="image/png")
                contents.append(image_part)
            except Exception as e:
                logger.warning(f"Failed to process image attachment: {e}")
                contents[0] += "\n[Error: Image attachment failed to load, rely on text]"

        try:
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

            result = self._safe_parse_json(raw_text)
            
            if result is None:
                raise ValueError(f"Failed to parse JSON from response: {raw_text[:200]}...")

            for k in result:
                if isinstance(result[k], str):
                    result[k] = self._clean_text(result[k])

            required_keys = ["latex", "reasoning", "final_answer", "confidence_score"]
            for key in required_keys:
                if key not in result:
                    logger.warning(f"Missing key {key} in Gemini response: {result.keys()}")
                    if key == "confidence_score":
                        result[key] = 0.0
                    else:
                         result[key] = "Error: Missing in response"
            
            # Inject model info
            result["model"] = "gemini"
            return result

        except Exception as e:
            logger.error(f"Gemini API call failed: {e}")
            raise
    async def generate_with_tools(
        self, 
        prompt: str, 
        tools: Optional[list] = None, 
        history: Optional[list] = None,
        tool_config: Optional[Dict] = None
    ) -> Any:
        """
        Generates content using Gemini with tool support (Function Calling).
        Returns the raw response object to let Orchestrator handle tool calls.
        """
        target_model = "gemini-2.5-flash" # Tools work well with Flash and it is generally available
        
        try:
            # Convert history to SDK format if needed, or rely on client.chats.create
            # For now, we'll use a stateless generate_content with history in contents if simple,
            # or better: use client.chats for multi-turn.
            
            # Let's use the efficient generate_content with a list of messages
            contents = []
            
            if history:
                contents.extend(history)
            
            contents.append(types.Content(role="user", parts=[types.Part.from_text(text=prompt)]))

            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=target_model,
                contents=contents,
                config=types.GenerateContentConfig(
                    tools=tools,
                    tool_config=tool_config,
                    temperature=0.0 # Strict for tools
                )
            )
            return response

        except Exception as e:
            logger.error(f"Gemini Tool Generation failed: {e}")
            raise
