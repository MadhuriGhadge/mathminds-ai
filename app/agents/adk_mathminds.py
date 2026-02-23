import logging
import asyncio
import base64
import json
from typing import Optional, AsyncGenerator, Dict, Any

from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.genai import types
from google.genai.errors import ClientError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.core.settings import settings
from app.core.llm_guard import check_and_increment
from app.tools.web_scraper import WebScraper
from app.tools.symbolic_solver import SymbolicSolver
from app.tools.similarity_search import SimilarProblemFinder
from app.tools.python_executor import PythonInterpreter
from app.core.math_normalizer import MathQueryNormalizer

logger = logging.getLogger(__name__)


class MathMindsADKAgent:
    """
    Agent-based architecture using Google ADK.
    Supports real-time streaming of reasoning steps and final answers.
    """

    def __init__(self, model_name: str = "gemini-2.0-flash", redis_client=None):
        self.api_key = settings.GOOGLE_API_KEY
        self.redis_client = redis_client

        if not self.api_key:
            logger.warning("No Google API Key found. Agent will fail.")

        # Tool instances
        self.web_scraper = WebScraper(headless=True)
        self.symbolic_solver = SymbolicSolver()
        self.normalizer = MathQueryNormalizer()
        self.similar_finder = SimilarProblemFinder()
        self.python_executor = PythonInterpreter()

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

        async def execute_python(code: str) -> str:
            """
            Execute arbitrary Python code for simulations, complex logic, or data analysis.
            Use this when SymPy is too restrictive or you need to run a simulation.
            Args:
                code: The Python code to execute.
            """
            result = await self.python_executor.execute(code)
            if result.get("status") == "success":
                return f"Output:\n{result.get('content')}\nResult: {result.get('result')}"
            return f"Error in Python execution: {result.get('content')}"

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

        # ── Agent & Runner ────────────────────────────────────────────────────
        self.agent = Agent(
            name="math_minds_core",
            model=model_name,
            tools=[web_search, math_solver, execute_python, find_similar_problems],
            instruction=(
                "You are MathMinds AI, a precise mathematical assistant. "
                "You can see images natively! When an image is provided, examine it "
                "carefully to extract equations, count objects, or interpret graphs. "
                "\n\nCRITICAL: Always start by explaining your step-by-step approach "
                "before using any tools. Your internal monologue should be clear "
                "and explain the reasoning behind your tool choices."
            )
        )

        self.session_service = InMemorySessionService()
        self.runner = Runner(
            app_name="mathminds",
            agent=self.agent,
            session_service=self.session_service
        )

        logger.info(f"MathMindsADKAgent initialized with model: {model_name}")

    async def solve(
        self,
        problem: str,
        image_data: Optional[str] = None,
        session_id: str = "default_session",
        user_id: str = "default_user"
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Streaming entry point. Yields events as they occur.
        """

        # ── 1. Daily quota check ──────────────────────────────────────────────
        if self.redis_client:
            allowed, used, limit = check_and_increment(self.redis_client, user_id)
            if not allowed:
                yield {"type": "error", "content": f"⚠️ Daily limit reached ({limit} today)."}
                return
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
        except Exception as e:
            logger.warning(f"Session setup warning: {e}")

        # ── 3. Build message parts ────────────────────────────────────────────
        parts = []
        if problem:
            parts.append(types.Part.from_text(text=problem))
        else:
            parts.append(types.Part.from_text(text="Analyze this image."))

        if image_data:
            try:
                img_bytes = base64.b64decode(image_data)
                mime_type = "image/png"  # Default
                # Basic sniff
                if image_data.startswith("/9j/"): mime_type = "image/jpeg"
                elif image_data.startswith("iVBORw"): mime_type = "image/png"
                
                parts.append(types.Part.from_bytes(data=img_bytes, mime_type=mime_type))
            except Exception as e:
                logger.error(f"Image decode failed: {e}")

        # ── 4. Run agent (Streaming) ──────────────────────────────────────────
        try:
            async for event in self.runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=types.Content(role="user", parts=parts)
            ):
                # ── Capture Reasoning / Thoughts ──
                if hasattr(event, "content") and event.content:
                    for part in event.content.parts:
                        if part.text:
                            # We treat intermittent text as reasoning/logic
                            yield {"type": "thought", "content": part.text}
                
                # ── Capture Tool Usage ──
                if hasattr(event, "tool_call") and event.tool_call:
                    yield {
                        "type": "action", 
                        "content": f"Using tool: {event.tool_call.function_call.name}"
                    }

                # ── Capture Tool Response ──
                if hasattr(event, "tool_response") and event.tool_response:
                     yield {
                        "type": "observation", 
                        "content": f"Obtained result from {event.tool_response.function_response.name}"
                    }

        except Exception as e:
            logger.error(f"Streaming execution failed: {e}")
            yield {"type": "error", "content": str(e)}
