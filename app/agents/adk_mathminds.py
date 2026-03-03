import logging
import asyncio
import base64
import json
import contextvars
from typing import Optional, AsyncGenerator, Dict, Any

from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.genai import types
from google.genai.errors import ClientError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.core.settings import settings
from app.core.llm_guard import check_and_increment
from app.tools.web_scraper import WebScraper
from app.tools.symbolic_solver import SymbolicSolver
from app.tools.similarity_search import SimilarProblemFinder
from app.tools.python_executor import PythonInterpreter
from app.tools.advanced_ocr import AdvancedOCR
from app.tools.vision_analyzer import VisionAnalyzer
from app.core.math_normalizer import MathQueryNormalizer

logger = logging.getLogger(__name__)


# Thread-safe context for the current image being processed
current_image_ctx = contextvars.ContextVar("current_image", default=None)

class MathMindsADKAgent:
    """
    Agent-based architecture using Google ADK.
    Supports real-time streaming of reasoning steps and final answers.
    """

    def __init__(self, model_name: str = "gemini-2.5-flash", redis_client=None):
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
        self.advanced_ocr = AdvancedOCR()
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

        async def image_interpreter() -> str:
            """
            Convert handwritten or printed math equations from the CURRENT image into machine-readable LaTeX/text.
            Use this for recognizing symbols, numbers, and formulas. 
            DO NOT use this for interpreting graphs, geometry, or spatial relationships.
            """
            image_data = current_image_ctx.get()
            if not image_data:
                return "Error: No image provided in current context."
            
            try:
                # Remove base64 prefix if present
                if "," in image_data:
                    image_data = image_data.split(",")[1]
                
                import base64
                img_bytes = base64.b64decode(image_data)
                text = self.advanced_ocr.process_image_bytes(img_bytes)
                return f"OCR result (LaTeX/Text): {text}" if text else "OCR failed to find text."
            except Exception as e:
                return f"Error in Image Interpreter: {str(e)}"

        async def statistical_vision(query: str) -> str:
            """
            Analyze the CURRENT image for objects, counting, grouping, and basic visual set statistics.
            Use this for 'How many...?' or 'Find all...'.
            DO NOT use this for coordinate extraction from line graphs, plot analysis, or geometry.
            Args:
                query: Specific question about the image (e.g., 'Count the red marbles').
            """
            image_data = current_image_ctx.get()
            if not image_data:
                return "Error: No image provided in current context."
            
            result = self.vision_analyzer.analyze(image_data, query)
            if result.get("status") == "success":
                quant = result.get("quantitative_analysis")
                if quant:
                    return f"Vision Analysis: Found {quant.get('total_objects')} objects. Details: {quant.get('objects')}"
                return "Vision Analysis: No specific objects counted. Use native vision for qualitative tasks."
            return f"Error in Statistical Vision: {result.get('error')}"

        def find_similar_problems(query: str) -> str:
            # ... existing similar finder logic ...
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
            tools=[
                web_search, math_solver, execute_python, 
                find_similar_problems, image_interpreter, statistical_vision
            ],
            instruction=(
                "You are MathMinds AI, a precise mathematical analytical assistant. "
                "\n\nVISION GUIDELINES:"
                "\n1. For HANDWRITTEN equations or text: ALWAYS call `image_interpreter` first. "
                "It provides specialized OCR precision that native vision might miss."
                "\n2. For COUNTING or OBJECT DETECTION: ALWAYS call `statistical_vision`. "
                "It uses specialized object detection (YOLO) for accurate quantification."
                "\n3. For GRAPHS, PLOTS, COORDINATE GEOMETRY, or LOG DIAGRAMS: DO NOT use specialized tools. "
                "Rely on your NATIVE MULTIMODAL VISION to interpret coordinates, slopes, and trends directly."
                "\n4. Once you have machine-readable data from these tools, use `math_solver` or "
                "`execute_python` to finalize the solution."
                "\n\nCRITICAL: Always explain your reasoning before and after using tools."
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

        # ── 1. Set Image Context ──────────────────────────────────────────────
        token = current_image_ctx.set(image_data)
        
        try:
            # ── 2. Daily quota check ──────────────────────────────────────────────
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
            async for event in self.runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=types.Content(role="user", parts=parts),
                run_config=RunConfig(streaming_mode=StreamingMode.SSE)
            ):
                # ── Determine Event Type ──
                # is_final_response() is usually True for the final user-facing text
                try:
                    is_final = event.is_final_response()
                except Exception:
                    is_final = False
                
                # ── Capture Content (Text) ──
                if hasattr(event, "content") and event.content and event.content.parts:
                    for part in event.content.parts:
                        if hasattr(part, "text") and part.text:
                            # Stream ALL text to the main answer window
                            # This fixes the "empty answer until refresh" issue.
                            yield {"type": "answer", "content": part.text}
                            
                            # Log terminal responses separately if needed for logic
                            if is_final:
                                logger.debug(f"Final response chunk received: {part.text[:50]}...")
                
                # ── Capture Tool Usage (Reasoning) ──
                for fc in event.get_function_calls():
                    yield {
                        "type": "action", 
                        "content": f"Using tool: {fc.name}"
                    }

                # ── Capture Tool Response ──
                for fr in event.get_function_responses():
                     yield {
                        "type": "observation", 
                        "content": f"Obtained result from {fr.name}"
                    }

        except Exception as e:
            logger.error(f"Streaming execution failed: {e}")
            yield {"type": "error", "content": str(e)}
        finally:
            try:
                current_image_ctx.reset(token)
            except ValueError:
                # This can happen if the generator is closed (GeneratorExit) 
                # in a different task context than where it was started.
                pass
