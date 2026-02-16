

import logging
import asyncio
import base64
from typing import Optional, Dict, Any, List

from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.genai import types

from app.core.settings import settings
from app.tools.web_scraper import WebScraper
from app.tools.symbolic_solver import SymbolicSolver
from app.tools.similarity_search import SimilarProblemFinder
from app.core.ocr import OCRProcessor
from app.tools.vision_analyzer import VisionAnalyzer
from app.core.math_normalizer import MathQueryNormalizer

logger = logging.getLogger(__name__)

class MathMindsADKAgent:
    """
    Agent-based architecture using Google ADK (GitHub version).
    Refined to match official Multitool Agent documentation patterns.
    """

    def __init__(self, model_name: str = "gemini-2.5-pro"):
        self.api_key = settings.GOOGLE_API_KEY
        if not self.api_key:
            logger.warning("No Google API Key found. Agent will fail.")

        # Initialize Tool Instances
        self.web_scraper = WebScraper(headless=True)
        self.symbolic_solver = SymbolicSolver()
        self.normalizer = MathQueryNormalizer()
        self.similar_finder = SimilarProblemFinder()
        self.ocr = OCRProcessor()
        self.vision_analyzer = VisionAnalyzer()

        # Define Tools as simpler closures
        # Docs pattern: simple functions, passed in a list.
        async def web_search(query: str) -> str:
            """
            Useful for finding current events, prices, weather, and general information from the internet.
            
            Args:
                query: The search query.
            """
            result = await self.web_scraper.scrape(query)
            if result.get("status") == "success":
                return result.get("content", "No content found.")
            else:
                return f"Error searching web: {result.get('error')}"

        def math_solver(problem: str) -> str:
            """
            Useful for solving symbolic math problems like equations, derivatives, integrals, and simplification.
            
            Args:
                problem: The math problem description or expression.
            """
            intent = self.normalizer.normalize(problem)
            query_obj = intent if intent else problem
            result = self.symbolic_solver.solve(query_obj)
            
            if result.get("status") == "success":
                return result.get("content", "No solution found.")
            else:
                return f"Error solving math: {result.get('error')}"

        def find_similar_problems(query: str) -> str:
            """
            Useful for finding similar math problems and their solutions from the database to learn how they were solved.
            Use this when you are stuck or want to see examples.
            
            Args:
                query: The math problem to find similar examples for.
            """
            results = self.similar_finder.search(query, limit=2)
            if not results:
                return "No similar problems found."
            
            formatted = "Here are some similar problems and their solutions:\n"
            for item in results:
                formatted += f"Problem: {item.get('problem_text')}\nSolution: {item.get('solution_text')}\n---\n"
            return formatted

        def read_image(image_data: str) -> str:
            """
            Useful for reading text, numbers, or equations from an image when you cannot see it clearly or need the exact text.
            
            Args:
                image_data: The base64 string of the image.
            """
            try:
                text = self.ocr.extract_text(image_data=image_data)
                return text if text else "No text found in image."
            except Exception as e:
                return f"Error reading image: {str(e)}"
        
        async def analyze_image(image_data: str, focus: str = "") -> str:
            """
            Analyzes an image mathematically: extracts equations, counts objects, describes graphs, etc.
            Use this when the user uploaded an image and wants to count items or understand the visual content.
            
            Args:
                image_data: The base64 string of the image.
                focus: Option string to focus analysis (e.g. "count red balls").
            """
            try:
                result = self.vision_analyzer.analyze(image_data, focus)
                return str(result)
            except Exception as e:
                return f"Image analysis failed: {str(e)}"

        # Initialize Agent
        # Using 'Agent' class as per official docs, passing functions directly.
        self.agent = Agent(
            name="math_minds_core",
            model=model_name,
            tools=[web_search, math_solver, find_similar_problems, read_image, analyze_image], # Passed directly as function list
            instruction=(
                "You are MathMinds AI, a helpful and precise mathematical assistant. "
                "You can receive BOTH text instructions AND images in the same query. "
                "When an image is provided, ALWAYS analyze it first — describe what you see, "
                "extract equations if present, count objects if it's a probability/statistics question, "
                "or interpret graphs/charts/diagrams mathematically. "
                "Then combine the image analysis with the text prompt to give a complete answer. "
                "Use tools only when necessary (e.g. 'Math Solver' for symbolic work, 'Web Search' for facts). "
                "Use 'Read Image' to extract text from images if it's blurry or you need exact wording. "
                "Use 'Analyze Image' to count objects or detect items. "
                "Always explain your steps clearly and show reasoning."
            )
        )
        
        # Session Service
        self.session_service = InMemorySessionService()
        
        # Runner
        self.runner = Runner(
            app_name="mathminds",
            agent=self.agent,
            session_service=self.session_service
        )

        logger.info("MathMindsADKAgent initialized successfully (Doc Standard).")

    async def solve(self, problem: str, image_data: Optional[str] = None, session_id: str = "default_session", user_id: str = "default_user") -> str:
        """
        Main entry point for the agent to solve a problem.
        """
        # IDs are now passed in, with fallbacks for backward compatibility
        
        try:
            # Ensure session exists (create if not found)
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
                except Exception as create_err:
                     logger.warning(f"Session creation issue (might already exist): {create_err}")

            # Construct Message Parts
            parts = []
            parts.append(types.Part.from_text(text=problem))
            
            if image_data:
                try:
                    # Better MIME type detection
                    if image_data.startswith("/9j/"):
                        mime_type = "image/jpeg"
                    elif image_data.startswith("iVBORw"):
                        mime_type = "image/png"
                    elif image_data.startswith("R0lGOD"):
                        mime_type = "image/gif"
                    elif image_data.startswith("UklGR"):
                        mime_type = "image/webp"
                    else:
                        mime_type = "image/png" # Default fallback
                        
                    img_bytes = base64.b64decode(image_data)
                    parts.append(types.Part.from_bytes(data=img_bytes, mime_type=mime_type))
                    logger.info("Attached image to agent request.")
                except Exception as e:
                    logger.error(f"Failed to process image data: {e}")
                    parts.append(types.Part.from_text(text="[Error: attached image could not be processed]"))

            # Execute Agent
            response_text = ""
            async for event in self.runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=types.Content(role="user", parts=parts)
            ):
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if part.text:
                            response_text += part.text
            
            return response_text

        except Exception as e:
            logger.error(f"ADK Agent execution failed: {e}")
            return f"Error processing request: {str(e)}"
