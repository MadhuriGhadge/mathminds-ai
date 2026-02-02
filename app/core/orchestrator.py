import logging
import time
from typing import Any, Dict, Optional
import asyncio

from app.core.input_processor import InputProcessor, InputType
from app.memory.cache import CacheManager
from app.memory.database import DatabaseManager
from app.reasoning.gemini_client import GeminiSolver
from app.utils.hashing import generate_problem_hash
from app.validation.answer_checker import AnswerValidator
from app.core.errors import ErrorCodes, ERROR_MESSAGES
from app.core.router import QueryRouter, RouteType
from app.tools.web_scraper import WebScraper
from app.tools.symbolic_solver import SymbolicSolver
from app.tools.symbolic_solver import SymbolicSolver
from app.reasoning.classifier import QueryClassifier
from app.tools.vision_analyzer import VisionAnalyzer

logger = logging.getLogger(__name__)

class Orchestrator:
    """
    Main coordinator for the MathMinds AI Brain.
    Integrates input processing, memory, reasoning, and validation.
    """

    def __init__(self, cache_manager: Optional[CacheManager] = None, db_manager: Optional[DatabaseManager] = None):
        """
        Initialize all sub-components.
        Args:
            cache_manager: Injectable CacheManager (singleton).
            db_manager: Injectable DatabaseManager (singleton).
        """
        try:
            self.input_processor = InputProcessor()
            # If not provided, create fresh ones (backward compat or for tests)
            # Ideally, these should always be provided by DI
            self.cache_manager = cache_manager or CacheManager()
            self.db_manager = db_manager or DatabaseManager()
            self.solver = GeminiSolver()
            self.validator = AnswerValidator()
            
            # Smart Routing Tools
            self.router = QueryRouter()
            self.web_scraper = WebScraper()
            self.symbolic_solver = SymbolicSolver()
            self.router = QueryRouter()
            self.web_scraper = WebScraper()
            self.symbolic_solver = SymbolicSolver()
            self.classifier = QueryClassifier()
            # Defer loading to avoid startup lag if model not present, but for now init here.
            # Make sure it's non-blocking or simple load.
            self.vision_analyzer = VisionAnalyzer()
        except Exception as e:
            logger.critical(f"Failed to initialize Orchestrator components: {e}")
            raise

    async def process_problem(self, text: Optional[str] = None, image: Optional[str] = None, request_id: Optional[str] = None, model_preference: str = "fast", session_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Orchestrates the problem solving pipeline.

        Pipeline:
        1. Process & Validate Input (Text + Image)
        2. Hash Input
        3. Cache/DB Lookup
        4. Solve (if needed)
        5. Validate Answer
        6. Store & Cache
        7. Return Result

        Args:
            text: The optional problem string.
            image: The optional image (Base64 or URL).
            request_id: Optional UUID for request tracing.
            model_preference: 'fast' (Flash) or 'reasoning' (Pro).

        Returns:
            Dict[str, Any]: The final result including answer, metadata, and status.
        """
        start_time = time.time()
        result = {
            "status": "error",
            "answer": None,
            "error_code": None,
            "error_msg": None,
            "metadata": {
                "request_id": request_id, 
                "stage": "init",
                "model_used": model_preference
            }
        }

        # 1. Input Processing
        try:
            result["metadata"]["stage"] = "input_processing"
            logger.info("Step 1: Processing input", extra={"request_id": request_id, "step": 1})
            
            # Use compound processor
            processed_input = self.input_processor.process_compound(text_input=text, image_input=image)
            
            # Construct a representation for logging/storage
            user_input_repr = text or ""
            if image:
                user_input_repr += " [IMAGE_ATTACHED]"
            
            if not processed_input.is_valid:
                logger.warning(f"[{request_id}] Invalid input: {processed_input.error_message}")
                result["error"] = processed_input.error_message
                return result
            
            # Input type check: We support TEXT, LATEX, BASE64_IMAGE, IMAGE_URL, MULTIMODAL
            # Logic is handled by InputProcessor and Solver
            pass

        except Exception as e:
            logger.error(f"[{request_id}] Input processing failed: {e}")
            result["error_code"] = ErrorCodes.INPUT_VALIDATION_ERROR
            result["error_msg"] = ERROR_MESSAGES[ErrorCodes.INPUT_VALIDATION_ERROR]
            result["metadata"]["_internal_debug"] = str(e)
            return result

        # 2. Hashing
        try:
            result["metadata"]["stage"] = "hashing"
            logger.info("Step 2: Generating hash", extra={"request_id": request_id, "step": 2})
            
            # Start with cleaned content (OCR text or user text)
            hash_input = processed_input.cleaned_content
            
            # If image data is present, append its hash to ensure uniqueness
            # This prevents different images with same OCR (or empty OCR) from colliding
            if processed_input.metadata and "image_data" in processed_input.metadata:
                import hashlib
                image_data = processed_input.metadata["image_data"]
                if image_data:
                    # We use a fast hash of the base64 string
                    img_hash = hashlib.md5(image_data.encode('utf-8')).hexdigest()
                    hash_input = f"{hash_input}|image:{img_hash}"
            
            problem_hash = generate_problem_hash(hash_input)
            result["metadata"]["hash"] = problem_hash
        except Exception as e:
            logger.error(f"[{request_id}] Hashing failed: {e}")
            result["error_code"] = ErrorCodes.INTERNAL_ERROR
            result["error_msg"] = ERROR_MESSAGES[ErrorCodes.INTERNAL_ERROR]
            result["metadata"]["_internal_debug"] = str(e)
            return result

        # 3. Memory Lookup (Cache & DB)
        
        # 3a. Cache Lookup
        try:
            result["metadata"]["stage"] = "cache_lookup"
            logger.info("Step 3: Checking cache", extra={"request_id": request_id, "hash": problem_hash, "step": 3})
            cached_answer = self.cache_manager.get_cached_answer(problem_hash)
            if cached_answer:
                logger.info("Cache hit", extra={"request_id": request_id, "hash": problem_hash, "source": "cache"})
                result["status"] = "success"
                result["answer"] = cached_answer
                result["metadata"]["source"] = "cache"
                result["metadata"]["latency"] = time.time() - start_time
                return result
        except Exception as e:
            logger.error(f"[{request_id}] Cache lookup failed: {e}")
            # Fail open to DB
        
        # 3b. DB Lookup
        try:
            result["metadata"]["stage"] = "db_lookup"
            logger.info("Step 3b: Checking database", extra={"request_id": request_id, "hash": problem_hash, "step": "3b"})
            db_record = self.db_manager.find_by_hash(problem_hash)
            if db_record and "answer" in db_record:
                logger.info("Database hit", extra={"request_id": request_id, "hash": problem_hash, "source": "database"})
                answer_data = db_record["answer"]
                
                # Re-populate cache for future speed (Safe: Atomic if not exists)
                try:
                    self.cache_manager.set_if_not_exists(problem_hash, answer_data)
                except Exception as cache_err:
                     logger.warning(f"[{request_id}] Failed to repopulate cache: {cache_err}")

                result["status"] = "success"
                result["answer"] = answer_data
                result["metadata"]["source"] = "database"
                result["metadata"]["latency"] = time.time() - start_time
                return result

        except Exception as e:
            logger.error(f"[{request_id}] Database lookup failed: {e}")
            # Fail open to Solver
            
        
        # 4. Smart Routing & Reasoning
        try:
            result["metadata"]["stage"] = "reasoning"
            logger.info("Step 4: Smart Routing & Solving", extra={"request_id": request_id, "step": 4})
            
            # 4a. Route & Execute Tools
            tool_context = ""
            if not image: # Only route text queries for now, or if multimodal has text
                 route = self.router.route(processed_input.cleaned_content)
                 result["metadata"]["route"] = route.value
                 
                 if route == RouteType.WEB:
                     logger.info("Executing Web Scraper...")
                     
                     # Refine with Classifier
                     # Run in thread to avoid blocking
                     classification = await asyncio.to_thread(self.classifier.classify, processed_input.cleaned_content)
                     
                     query_to_use = processed_input.cleaned_content
                     focus = None
                     
                     if classification.get("requires_web_search"):
                         queries = classification.get("search_queries", [])
                         if queries:
                             query_to_use = queries[0]
                         focus = classification.get("extraction_focus")
                         
                     scrape_res = await self.web_scraper.scrape(query_to_use, extraction_focus=focus)
                     if scrape_res.get("status") == "success":
                         tool_context = f"\n\n[Web Data Context]:\n{scrape_res.get('content')}\nSource: {scrape_res.get('url')}\n"
                         
                 elif route == RouteType.SYMBOLIC:
                     logger.info("Executing Symbolic Solver...")
                     # Run in thread to avoid blocking event loop
                     sym_res = await asyncio.to_thread(self.symbolic_solver.solve, processed_input.cleaned_content)
                     if sym_res.get("status") == "success":
                         tool_context = f"\n\n[Symbolic Verification]:\n{sym_res.get('content')}\n"

            # 4b. Solve with Gemini
            # Extract image data if available
            image_data = None
            if processed_input.metadata and "image_data" in processed_input.metadata:
                image_data = processed_input.metadata["image_data"]
                
            # Combine input with tool context
            final_prompt = processed_input.cleaned_content + tool_context

            # Mathematical Vision (YOLO)
            if image and self.vision_analyzer:
                 # Cleaned content is the text query part if multimodal
                 # We assume we have the raw base64 in processed_input.metadata if it was processed
                 image_for_vision = None
                 if processed_input.metadata and "image_data" in processed_input.metadata:
                     image_for_vision = processed_input.metadata["image_data"]
                 
                 if image_for_vision:
                    logger.info("Executing Mathematical Vision (YOLO)...")
                    vision_res = self.vision_analyzer.analyze(image_for_vision, processed_input.cleaned_content)
                    
                    if vision_res.get("status") == "success" and vision_res.get("vision_mode") == "quantitative":
                        quant = vision_res.get("quantitative_analysis", {})
                        objects = quant.get("objects", {})
                        
                        if objects:
                            # format as a clear list
                            desc = "YOLO Quantitative Analysis (High Precision):\n"
                            desc += f"Total Objects Detected: {quant.get('total_objects', 0)}\n"
                            desc += f"Average Confidence: {quant.get('avg_confidence', 0.0)}\n"
                            desc += "Detailed Counts (Color + Type):\n"
                            for obj_type, count in objects.items():
                                desc += f"- {obj_type}: {count}\n"
                            
                            final_prompt += f"\n\n[{desc}]\n"
                        else:
                             final_prompt += "\n\n[YOLO Analysis: No specific objects detected for counting]\n"

            # Inject History if session_id is present
            if session_id:
                history = self.db_manager.get_chat_history(session_id, limit=5)
                if history:
                    history_context = "\n\n[Chat History]:\n"
                    for msg in history:
                         role = msg.get('role', 'unknown')
                         content = msg.get('content', '')
                         history_context += f"{role}: {content}\n"
                    final_prompt = history_context + "\n[Current Request]: " + final_prompt
                
            # Determine model to use
            # Map preference 'reasoning' to a stronger model if available, else standard
            # Ideally 'gemini-1.5-pro' or 'gemini-2.0-flash-thinking-exp' if available
            # For now, we will map 'reasoning' to 'gemini-1.5-pro' and 'fast' to 'gemini-2.5-flash'
            target_model = "gemini-2.5-flash"
            if model_preference == "reasoning":
                target_model = "gemini-1.5-pro"
            
            # We pass the cleaned content (text/OCR) AND the raw image data if present
            generated_solution = await self.solver.solve(final_prompt, image_data=image_data, model_name=target_model)
        except Exception as e:
            logger.error(f"[{request_id}] Solver failed: {e}")
            result["error_code"] = ErrorCodes.GEMINI_ERROR
            result["error_msg"] = ERROR_MESSAGES[ErrorCodes.GEMINI_ERROR]
            result["metadata"]["_internal_debug"] = str(e)
            return result


        # 5. Validation
        try:
            logger.info("Step 5: Validating answer")
            is_valid, validation_errors = self.validator.validate(
                generated_solution, 
                is_math_problem=(
                    processed_input.input_type in [InputType.LATEX, InputType.BASE64_IMAGE, InputType.IMAGE_URL] 
                    or "math" in processed_input.cleaned_content.lower()
                ) # Simple heuristic or rely on processed_input
            )

            if not is_valid:
                logger.warning(f"Validation failed: {validation_errors}")
                result["error_code"] = ErrorCodes.GEMINI_ERROR # Or Validation Error
                result["error_msg"] = f"Generated answer failed validation."
                result["metadata"]["validation_errors"] = validation_errors
                # We do NOT store invalid answers
                return result

        except Exception as e:
            logger.error(f"Validation step failed: {e}")
            result["error_code"] = ErrorCodes.INTERNAL_ERROR
            result["error_msg"] = ERROR_MESSAGES[ErrorCodes.INTERNAL_ERROR]
            result["metadata"]["_internal_debug"] = str(e)
            return result

        # 6. Storage & Caching
        try:
            logger.info("Step 6: Storing result")
            
            problem_data = {
                "hash": problem_hash,
                "original_input": user_input_repr,
                "cleaned_content": processed_input.cleaned_content,
                "input_type": processed_input.input_type.value,
            }
            
            # Save to DB
            self.db_manager.save_problem(problem_data, generated_solution)
            
            # Save to Session History
            if session_id:
                # Save User Query
                self.db_manager.save_chat_message(session_id, "user", processed_input.cleaned_content)
                # Save AI Response (extract text from solution structure)
                # generated_solution might be a dict, need to extract text.
                # Assuming generated_solution has a 'text' or we dump it.
                # GeminiSolver returns Dict. Let's assume it has 'content' or 'text'.
                # Checking GeminiSolver (not viewed, but standard is dict).
                # If it's the standard format: {"text": "...", ...}
                ai_text = generated_solution.get("text") or str(generated_solution)
                self.db_manager.save_chat_message(session_id, "model", ai_text)
            
            # Save to Cache
            self.cache_manager.set_cached_answer(problem_hash, generated_solution)

        except Exception as e:
            logger.error(f"Storage failed: {e}")
            # We don't fail the request if storage fails, we just return the answer

        # 7. Return Result
        result["status"] = "success"
        result["answer"] = generated_solution
        result["metadata"]["source"] = "generated"
        result["metadata"]["latency"] = time.time() - start_time
        
        return result
