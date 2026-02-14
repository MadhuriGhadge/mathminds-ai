import logging
import time
import asyncio
import re
from typing import Any, Dict, Optional, List
from enum import Enum

from app.core.input_processor import InputProcessor
from app.memory.cache import CacheManager
from app.memory.database import DatabaseManager
from app.models.gemini import GeminiModel
from app.models.qwen import QwenModel
from app.utils.hashing import generate_problem_hash
from app.validation.answer_checker import AnswerValidator
from app.tools.web_scraper import WebScraper
from app.worker import scrape_web_task # Celery Task
from app.tools.symbolic_solver import SymbolicSolver
from app.tools.vision_analyzer import VisionAnalyzer
from app.tools.similarity_search import SimilarProblemFinder
from app.core.math_normalizer import MathQueryNormalizer
from app.core.settings import settings
from app.agents.adk_mathminds import MathMindsADKAgent

logger = logging.getLogger(__name__)

# --- Intent Enums ---
class IntentType(Enum):
    ARITHMETIC = "arithmetic"
    SYMBOLIC_MATH = "symbolic_math"
    VISION = "vision"
    SEARCH = "search"
    CONCEPTUAL = "conceptual"
    UNKNOWN = "unknown"

class Orchestrator:
    """
    Deterministic Orchestrator for MathMinds AI.
    Flow: Input -> Classify -> Route -> Solve -> Explain.
    """

    def __init__(self, cache_manager: Optional[CacheManager] = None, db_manager: Optional[DatabaseManager] = None):
        try:
            self.input_processor = InputProcessor()
            self.cache_manager = cache_manager or CacheManager()
            self.db_manager = db_manager or DatabaseManager()
            
            # Models
            self.gemini = GeminiModel()
            self.qwen = QwenModel()
            
            # Tools
            self.web_scraper = WebScraper()
            self.symbolic_solver = SymbolicSolver()
            self.vision_analyzer = VisionAnalyzer()
            self.similarity_finder = SimilarProblemFinder()
            self.math_normalizer = MathQueryNormalizer()
            
            # Agents
            self.adk_agent = MathMindsADKAgent()
            
        except Exception as e:
            logger.critical(f"Failed to initialize Orchestrator: {e}")
            raise

    def _classify_intent(self, text: str, has_image: bool) -> IntentType:
        """
        Fast, rule-based intent classifier. No LLM used here.
        """
        if has_image:
            return IntentType.VISION
            
        if not text:
            return IntentType.UNKNOWN
            
        text = text.lower().strip()
        
        # 1. Search Intent
        if any(w in text for w in ["price of", "news", "latest", "who is", "weather", "stock", "search for"]):
            return IntentType.SEARCH
            
        # 2. Arithmetic (Target Symbolic)
        # Check if purely numbers/operators/basic math keywords
        if re.match(r'^[\d\s\+\-\*\/\^\(\)\.\=]+$', text):
            return IntentType.ARITHMETIC
            
        # 3. Symbolic Math (Target Symbolic)
        math_keywords = ["solve", "integrate", "derive", "derivative", "limit", "sum", "simplify", "factor", "equation", "latex"]
        if any(w in text for w in math_keywords) or "=" in text or "\\" in text: # Latex has backslashes
            return IntentType.SYMBOLIC_MATH

        # 4. Conceptual/General (Target LLM)
        return IntentType.CONCEPTUAL

    async def process_problem(self, text: Optional[str] = None, image: Optional[str] = None, request_id: Optional[str] = None, model_preference: str = "fast", session_id: Optional[str] = None, user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Main Deterministic Pipeline.
        """
        start_time = time.time()
        request_id = request_id or "unknown"
        
        
        # --- User Context ---
        user_context_str = ""
        if user_id:
             try:
                 profile = self.db_manager.get_user_profile(user_id)
                 if profile:
                     level = profile.get("math_level", "Student")
                     interests = ", ".join(profile.get("interests", []))
                     user_context_str = f"User Profile: {level} level."
                     if interests:
                         user_context_str += f" Interests: {interests}."
                     user_context_str += " Adjust explanation complexity to match this level."
             except Exception as e:
                 logger.warning(f"Failed to fetch profile in orchestrator: {e}")
        
        # --- Strict Output Schema ---
        result_schema = {
            "request_id": request_id,
            "status": "error",
            "problem_type": "unknown",
            "source": "unknown",
            "answer": None,
            "steps": [],
            "explanation": None,
            "confidence": 0.0,
            "cached": False,
            "metadata": {
                "latency_ms": 0,
                "model": None,
                "tools_used": []
            }
        }

        try:
            # 1. Input Processing
            processed = self.input_processor.process_compound(text_input=text, image_input=image)
            if not processed.is_valid:
                result_schema["explanation"] = processed.error_message
                return self._finalize_result(result_schema, start_time)

            # 2. Routing (Agent vs Deterministic)
            if model_preference == "agent":
                try:
                    logger.info("Routing to Google ADK Agent")
                    agent_res = await self.adk_agent.solve(processed.cleaned_content, processed.metadata.get("image_data"))
                    
                    # Agent returns a string usually, we need to wrap it
                    result_schema["status"] = "success"
                    result_schema["source"] = "google_adk_agent"
                    result_schema["answer"] = agent_res
                    result_schema["explanation"] = "Solved by AI Agent using tools (Google ADK)."
                    result_schema["metadata"]["model"] = "gemini-flash-adk"
                    
                    return self._finalize_result(result_schema, start_time)
                except Exception as e:
                    logger.error(f"Agent failed: {e}")
                    result_schema["error"] = str(e)
                    # Fallback to standard flow? No, report error for explicit preference.
                    return self._finalize_result(result_schema, start_time)

            # 3. Hashing & Cache
            image_data = processed.metadata.get("image_data")
            p_hash = generate_problem_hash(processed.cleaned_content, image_data)
            lock_acquired = False
            lock_key = f"lock:{p_hash}"

            if settings.ENABLE_CACHE:
                cached = self.cache_manager.get_cached_answer(p_hash)
                if cached:
                    # Hydrate schema from cache
                    result_schema.update(cached)
                    result_schema["status"] = "success"
                    result_schema["cached"] = True
                    result_schema["source"] = "cache"
                    return self._finalize_result(result_schema, start_time)

                # --- CACHE STAMPEDE PROTECTION ---
                # Try to acquire a lock to prevent multiple workers from solving the same problem
                if self.cache_manager.redis_client:
                    # Try to acquire lock (set if not exists with 300s TTL)
                    is_locked = self.cache_manager.redis_client.set(lock_key, "locked", ex=300, nx=True)
                    
                    if is_locked:
                        lock_acquired = True
                    else:
                        # Lock exists -> another process is working. Wait for it.
                        logger.info(f"Problem {p_hash[:8]} is being processed by another worker. Waiting...")
                        for _ in range(300): # Wait up to 60 seconds (300 * 0.2)
                            await asyncio.sleep(0.2)
                            # Check cache again
                            cached = self.cache_manager.get_cached_answer(p_hash)
                            if cached:
                                logger.debug("Cache populated while waiting. Returning result.") # Using debug to reduce noise
                                result_schema.update(cached)
                                result_schema["status"] = "success"
                                result_schema["cached"] = True
                                result_schema["source"] = "cache"
                                return self._finalize_result(result_schema, start_time)
                        
                        # Timeout reached. One last check before giving up.
                        cached_final = self.cache_manager.get_cached_answer(p_hash)
                        if cached_final:
                            logger.info("Cache populated just in time. Returning result.")
                            result_schema.update(cached_final)
                            result_schema["status"] = "success"
                            result_schema["cached"] = True
                            result_schema["source"] = "cache"
                            return self._finalize_result(result_schema, start_time)

                        # Still nothing? Fail Open.
                        logger.warning(f"Timeout waiting for lock on {p_hash[:8]}. Proceeding to compute locally (Fail Open).")
                        # We proceed to solve it ourselves. lock_acquired is False, so we won't release the other worker's lock.
            
            # Use try/finally to ensure lock release if we acquired it
            try:
                # ... existing logic follows ...
                pass 
            except Exception:
                raise
            # Note: The 'finally' block to release lock needs to wrap the entire solve process.
            # Since I can't easily wrap the *rest* of the function without indenting everything, 
            # I will release the lock explicitly before return points or use a flag.
            # Actually, to generate correct code structure with replacement, I need to wrap the rest.
            # ALTERNATIVE: I will insert the 'acquire' here, and handling 'release' might be tricky with ReplaceFileContent if I don't re-indent headers.
            # Strategy: I'll use the 'lock' only for the Heavy LLM parts?
            # No, strictly strictly, I should wrap. 
            # Let's simple release the lock at the end of the function.
            # I'll enable a flag `self.has_lock = True` if I acquired it. And in `finally` of the whole block I release it.
            # Wait, `process_problem` has a big `try/except`. I can use that.
            

            # 3. Classification
            has_image = bool(processed.metadata.get("image_data"))
            image_data = processed.metadata.get("image_data")
            intent = self._classify_intent(processed.cleaned_content, has_image)
            
            result_schema["problem_type"] = intent.value
            logger.info(f"Classified intent: {intent.value} | Input: {processed.cleaned_content[:50]}...")

            # 4. Routing & Execution
            
            # --- ROUTE: VISION ---
            if intent == IntentType.VISION:
                # Analyze Image
                vision_res = await asyncio.to_thread(self.vision_analyzer.analyze, image_data)
                
                if vision_res.get("math_detected"):
                    # Extracted math text -> Solve Symbolically
                    math_text = vision_res.get("latex", "") or vision_res.get("text", "")
                    logger.info(f"Vision detected math: {math_text}")
                    
                    sym_res = await asyncio.to_thread(self.symbolic_solver.solve, math_text)
                    if sym_res.get("status") == "success":
                         self._populate_success(result_schema, sym_res, "vision+symbolic")
                         result_schema["steps"] = ["Analyzed image with YOLO/OCR", f"Extracted: {math_text}"] + sym_res.get("steps", [])
                    else:
                        # Fallback to Gemini with Image
                        gem_res = await self._safe_llm_call(processed.cleaned_content, image_data=image_data)
                        self._populate_success(result_schema, gem_res, "vision+gemini")
                else:
                    # General Image -> Gemini
                    gem_res = await self._safe_llm_call(processed.cleaned_content, image_data=image_data)
                    self._populate_success(result_schema, gem_res, "gemini-vision")

            # --- ROUTE: MATH (Symbolic/Arithmetic) ---
            elif intent in [IntentType.SYMBOLIC_MATH, IntentType.ARITHMETIC]:
                # Try Symbolic Solver First
                normalized = self.math_normalizer.normalize(processed.cleaned_content)
                target = normalized if normalized else processed.cleaned_content
                
                sym_res = await asyncio.to_thread(self.symbolic_solver.solve, target)
                
                if sym_res.get("status") == "success":
                    self._populate_success(result_schema, sym_res, "symbolic_solver")
                else:
                    # Fallback to Gemini
                    logger.info("Symbolic solver failed, falling back to Gemini.")
                    
                    fallback_prompt = processed.cleaned_content
                    if user_context_str:
                        fallback_prompt = f"{user_context_str}\n\nProblem: {processed.cleaned_content}"
                        
                    gem_res = await self._safe_llm_call(fallback_prompt)
                    self._populate_success(result_schema, gem_res, "gemini-fallback")

            # --- ROUTE: SEARCH ---
            elif intent == IntentType.SEARCH:
                # Scrape via Celery
                try:
                    task = scrape_web_task.delay(processed.cleaned_content)
                    # Wait for result with timeout (blocking the request, but offloading CPU)
                    scrape_res = task.get(timeout=30)
                except Exception as e:
                    logger.error(f"Celery scrape task failed: {e}")
                    scrape_res = {"content": "", "error": str(e)}

                context = scrape_res.get("content", "")[:3000] # Limit context
                
                # Summarize with Gemini
                summary_prompt = f"Using this search data: {context}\n\nAnswer: {processed.cleaned_content}"
                if user_context_str:
                     summary_prompt = f"{user_context_str}\n\n{summary_prompt}"
                     
                gem_res = await self._safe_llm_call(summary_prompt)
                
                self._populate_success(result_schema, gem_res, "search+gemini")
                result_schema["metadata"]["tools_used"].append("web_scraper")

            # --- ROUTE: CONCEPTUAL (General) ---
            else:
                # Direct Gemini Call
                prompt = processed.cleaned_content
                if user_context_str:
                     prompt = f"{user_context_str}\n\nProblem: {processed.cleaned_content}"
                
                gem_res = await self._safe_llm_call(prompt)
                self._populate_success(result_schema, gem_res, "gemini-2.5-flash")

            # 5. Save & Index
            if result_schema["status"] == "success":
                # Save to Redis Cache (CRITICAL for lock waiters!)
                if settings.ENABLE_CACHE:
                     self.cache_manager.set_cached_answer(p_hash, result_schema)

                # Save to DB
                self.db_manager.save_problem(
                    {"hash": p_hash, "content": processed.cleaned_content}, 
                    result_schema
                )
                # Index
                if self.similarity_finder and result_schema["answer"]:
                    self.similarity_finder.index_problem(
                        processed.cleaned_content,
                        str(result_schema["answer"]),
                        {"model": result_schema["metadata"]["model"]}
                    )

            # Release lock if we acquired it
            if lock_acquired and self.cache_manager.redis_client:
                try:
                    self.cache_manager.redis_client.delete(lock_key)
                except Exception as e:
                    logger.warning(f"Failed to release lock {lock_key}: {e}")

            return self._finalize_result(result_schema, start_time)

        except Exception as e:
            logger.error(f"Orchestrator Error: {e}")
            
            # Release lock on error too
            if locals().get("lock_acquired") and self.cache_manager.redis_client:
                 try:
                    self.cache_manager.redis_client.delete(lock_key)
                 except Exception as release_err:
                    logger.warning(f"Failed to release lock {lock_key} in error handler: {release_err}")

            result_schema["explanation"] = f"Internal Error: {str(e)}"
            return self._finalize_result(result_schema, start_time)

    async def _safe_llm_call(self, prompt: str, image_data: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """
        Tries Gemini first. If 429/Resource Exhausted, falls back to local Qwen.
        """
        try:
            return await self.gemini.solve(prompt, image_data, **kwargs)
        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                logger.warning(f"Gemini Rate Limit (429) hit. Falling back to local Qwen. Error: {e}")
                # Fallback to Qwen
                # Qwen might not support images, so we strip it.
                try:
                    return await self.qwen.solve(prompt, image_data=None)
                except Exception as qwen_error:
                    logger.error(f"Fallback to Qwen also failed: {qwen_error}")
                    raise e # Raise original Gemini error if fallback fails to indicate overloaded state.
            
            # If not a rate limit error, re-raise immediately
            raise e

    def _populate_success(self, schema: Dict, source_res: Dict, source_name: str):
        """Helper to map source result to unified schema."""
        schema["status"] = "success"
        schema["source"] = source_name
        schema["answer"] = source_res.get("final_answer") or source_res.get("content") or source_res.get("text")
        # Ensure LaTeX
        schema["answer_latex"] = source_res.get("latex", schema["answer"]) # store latent for UI
        schema["steps"] = source_res.get("steps", [])
        if "reasoning" in source_res:
             schema["explanation"] = source_res["reasoning"]
        schema["confidence"] = source_res.get("confidence_score", 1.0)
        schema["metadata"]["model"] = source_res.get("model", "unknown")

    def _finalize_result(self, schema: Dict, start_time: float) -> Dict:
        """Calculates latency and returns final dict."""
        schema["metadata"]["latency_ms"] = int((time.time() - start_time) * 1000)
        return schema
