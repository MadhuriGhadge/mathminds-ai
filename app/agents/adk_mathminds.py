
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
from app.core.math_normalizer import MathQueryNormalizer

logger = logging.getLogger(__name__)

class MathMindsADKAgent:
    """
    Agent-based architecture using Google ADK (GitHub version).
    Refined to match official Multitool Agent documentation patterns.
    """

    def __init__(self, model_name: str = "gemini-2.5-flash"):
        self.api_key = settings.GOOGLE_API_KEY
        if not self.api_key:
            logger.warning("No Google API Key found. Agent will fail.")

        # Initialize Tool Instances
        self.web_scraper = WebScraper(headless=True)
        self.symbolic_solver = SymbolicSolver()
        self.normalizer = MathQueryNormalizer()

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

        # Initialize Agent
        # Using 'Agent' class as per official docs, passing functions directly.
        self.agent = Agent(
            name="math_minds_core",
            model=model_name,
            tools=[web_search, math_solver], # Passed directly as function list
            instruction=(
                "You are MathMinds AI, a helpful and precise mathematical assistant. "
                "You have access to tools for solving symbolic math problems and searching the web. "
                "If an image is provided, analyze it mathematically. "
                "Use 'Math Solver' for distinct math problems (equations, calculus, etc.). "
                "Use 'Web Search' for real-world data (prices, weather, facts). "
                "Always explain your steps clearly."
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

    async def solve(self, problem: str, image_data: Optional[str] = None) -> str:
        """
        Main entry point for the agent to solve a problem.
        """
        user_id = "default_user" # TODO: integrate with actual user auth
        session_id = "default_session" # TODO: integrate with session management

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
                    img_bytes = base64.b64decode(image_data)
                    mime_type = "image/png" 
                    if image_data.startswith("/9j/"):
                        mime_type = "image/jpeg"
                    
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
