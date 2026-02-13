import logging
import os
import json
import re
from typing import Dict, Any, Optional

from google import genai
from google.genai import types
import pybreaker
from tenacity import retry, stop_after_attempt, wait_random_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)

class QueryClassifier:
    """
    Classifies user queries to determine if they require web options
    and what specific information to extract.
    """

    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-2.5-flash"):
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            logger.warning("No API key provided for QueryClassifier.")
        
        self.client = genai.Client(api_key=self.api_key)
        self.model_name = model_name
        
        # Robustness
        self.breaker = pybreaker.CircuitBreaker(fail_max=5, reset_timeout=60)

    @retry(stop=stop_after_attempt(3), wait=wait_random_exponential(multiplier=1, max=60))
    def classify(self, query: str) -> Dict[str, Any]:
        """
        Classifies the query.
        """
        return self.breaker.call(self._classify_internal, query)

    def _classify_internal(self, query: str) -> Dict[str, Any]:
        prompt = f"""
        Analyze the following user query to determine if it requires external information (web search, live data, specific facts) or if it can be answered by a standard math/logic solver.

        If it requires web search, identify the specific 'extraction_focus' (the exact value or fact needed, e.g., 'stock price', 'release date', 'population').

        Query: "{query}"

        Output JSON format:
        {{
            "requires_web_search": boolean,
            "search_queries": ["list of optimal search queries"],
            "extraction_focus": "keyword or phrase to look for in the page content to find the answer",
            "intent": "general_info" | "specific_value" | "date_lookup"
        }}
        """

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.0
                )
            )
            
            if not response.text:
                return {"requires_web_search": False}

            return json.loads(response.text)
        except Exception as e:
            logger.error(f"Classification failed: {e}")
            # Fail safe to no search
            return {"requires_web_search": False}
