"""
adk_mathminds.py — MathMinds ADK Agent
Key changes vs original:
  1. Semaphore removed. Replaced with Redis-backed daily quota via llm_guard.
  2. Tenacity retries scoped to 429/rate-limit errors ONLY (not all exceptions),
     so a quota block is not retried.
  3. ADK event loop now filters for is_final_response() to avoid
     collecting tool-call intermediate text.
  4. Redis client injected via constructor so it can be shared with CacheManager.
"""

import logging
import asyncio
import base64
from typing import Optional

from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.genai import types
from google.genai.errors import ClientError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.core.settings import settings
from app.core.llm_guard import check_and_increment  # ← new import
from app.tools.web_scraper import WebScraper
from app.tools.symbolic_solver import SymbolicSolver
from app.tools.similarity_search import SimilarProblemFinder
from app.core.ocr import OCRProcessor
from app.tools.vision_analyzer import VisionAnalyzer
from app.core.math_normalizer import MathQueryNormalizer

logger = logging.getLogger(__name__)


class MathMindsADKAgent:
    """
    Agent-based architecture using Google ADK.
    Uses a Redis-backed daily quota (not a semaphore) to stay within 20 RPD.
    """

    def __init__(self, model_name: str = "gemini-2.5-flash", redis_client=None):
        self.api_key = settings.GOOGLE_API_KEY
        self.redis_client = redis_client  # injected — shared with CacheManager

        if not self.api_key:
            logger.warning("No Google API Key found. Agent will fail.")

        # Tool instances
        self.web_scraper = WebScraper(headless=True)
        self.symbolic_solver = SymbolicSolver()
        self.normalizer = MathQueryNormalizer()
        self.similar_finder = SimilarProblemFinder()
        self.ocr = OCRProcessor()
        self.vision_analyzer = VisionAnalyzer()

        # ── Tool definitions ──────────────────────────────────────────────────
        async def web_search(query: str) -> str:
            """
            Search the internet for current data: prices, news, weather, facts.
            Args:
                query: The search query.
            """
            result = await self.web_scraper.scrape(query)
            if result.get("status") == "success":
                return result.get("content", "No content found.")
            return f"Error searching web: {result.get('error')}"

        async def math_solver(problem: str) -> str:
            """
            Solve symbolic math: equations, derivatives, integrals, simplification.
            Args:
                problem: The math expression or description.
            """
            intent = self.normalizer.normalize(problem)
            query_obj = intent if intent else problem
            result = await self.symbolic_solver.solve(query_obj)
            if result.get("status") == "success":
                return result.get("content", "No solution found.")
            return f"Error solving math: {result.get('error')}"

        def find_similar_problems(query: str) -> str:
            """
            Find similar solved problems from the database for reference.
            Args:
                query: The math problem to find examples for.
            """
            results = self.similar_finder.search(query, limit=2)
            if not results:
                return "No similar problems found."
            formatted = "Similar problems:\n"
            for item in results:
                formatted += f"Problem: {item.get('problem_text')}\nSolution: {item.get('solution_text')}\n---\n"
            return formatted

        def read_image(image_data: str) -> str:
            """
            Extract text/equations from an image using OCR.
            Args:
                image_data: Base64 string of the image.
            """
            try:
                text = self.ocr.extract_text(image_data=image_data)
                return text if text else "No text found in image."
            except Exception as e:
                return f"Error reading image: {str(e)}"

        async def analyze_image(image_data: str, focus: str = "") -> str:
            """
            Analyze an image mathematically: count objects, describe graphs, extract equations.
            Args:
                image_data: Base64 string of the image.
                focus: Optional focus hint (e.g. 'count red balls').
            """
            try:
                result = self.vision_analyzer.analyze(image_data, focus)
                return str(result)
            except Exception as e:
                return f"Image analysis failed: {str(e)}"

        # ── Agent & Runner ────────────────────────────────────────────────────
        self.agent = Agent(
            name="math_minds_core",
            model=model_name,
            tools=[web_search, math_solver, find_similar_problems, read_image, analyze_image],
            instruction=(
                "You are MathMinds AI, a precise mathematical assistant. "
                "When an image is provided, analyze it first — extract equations, "
                "count objects, or interpret graphs. Then combine image analysis with "
                "the text prompt. Use tools only when needed. Show your reasoning clearly."
            )
        )

        self.session_service = InMemorySessionService()
        self.runner = Runner(
            app_name="mathminds",
            agent=self.agent,
            session_service=self.session_service
        )

        logger.info("MathMindsADKAgent initialized.")

    async def solve(
        self,
        problem: str,
        image_data: Optional[str] = None,
        session_id: str = "default_session",
        user_id: str = "default_user"
    ) -> str:
        """
        Main entry point. Enforces daily quota before calling the LLM.
        Returns the agent's answer string, or an error message.
        """

        # ── 1. Daily quota check ──────────────────────────────────────────────
        # This is the ONLY gate. One check per user question = one LLM call.
        if self.redis_client:
            allowed, used, limit = check_and_increment(self.redis_client, user_id)
            if not allowed:
                logger.warning(f"Quota blocked for user={user_id} ({used}/{limit} today)")
                return (
                    f"⚠️ Daily limit reached ({limit} questions per day). "
                    "Please try again tomorrow."
                )
        else:
            logger.warning("Redis unavailable — skipping quota check (failing open).")

        # ── 2. Session setup ──────────────────────────────────────────────────
        try:
            existing = await self.session_service.get_session(
                app_name="mathminds", session_id=session_id, user_id=user_id
            )
            if not existing:
                await self.session_service.create_session(
                    app_name="mathminds", user_id=user_id, session_id=session_id
                )
        except Exception:
            try:
                await self.session_service.create_session(
                    app_name="mathminds", user_id=user_id, session_id=session_id
                )
            except Exception as e:
                logger.warning(f"Session create warning: {e}")

        # ── 3. Build message parts ────────────────────────────────────────────
        parts = [types.Part.from_text(text=problem)]

        if image_data:
            try:
                if image_data.startswith("/9j/"):
                    mime_type = "image/jpeg"
                elif image_data.startswith("iVBORw"):
                    mime_type = "image/png"
                elif image_data.startswith("R0lGOD"):
                    mime_type = "image/gif"
                elif image_data.startswith("UklGR"):
                    mime_type = "image/webp"
                else:
                    mime_type = "image/png"

                img_bytes = base64.b64decode(image_data)
                parts.append(types.Part.from_bytes(data=img_bytes, mime_type=mime_type))
                logger.info("Image attached to agent request.")
            except Exception as e:
                logger.error(f"Failed to process image: {e}")
                parts.append(types.Part.from_text(text="[Error: image could not be processed]"))

        # ── 4. Run agent (retry on 429 only, not all exceptions) ─────────────
        @retry(
            stop=stop_after_attempt(2),          # max 2 attempts total
            wait=wait_exponential(multiplier=2, min=5, max=30),
            retry=retry_if_exception_type(ClientError),  # only retry on API errors
            reraise=True
        )
        async def run_agent_safely() -> str:
            outcome = ""
            async for event in self.runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=types.Content(role="user", parts=parts)
            ):
                # ✅ Only collect the final response, not tool-call intermediates
                if hasattr(event, "is_final_response") and event.is_final_response():
                    if event.content and event.content.parts:
                        for part in event.content.parts:
                            if part.text:
                                outcome += part.text
            return outcome

        try:
            response_text = await run_agent_safely()
            if not response_text:
                logger.warning("Agent returned empty response.")
                return "The agent completed but returned no text. Please rephrase your question."
            return response_text

        except Exception as e:
            logger.error(f"ADK Agent execution failed: {e}")
            return f"Error processing request: {str(e)}"