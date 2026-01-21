import logging
import time
from typing import Any, Dict, Optional

from app.core.input_processor import InputProcessor, InputType
from app.memory.cache import CacheManager
from app.memory.database import DatabaseManager
from app.reasoning.gemini_client import GeminiSolver
from app.utils.hashing import generate_problem_hash
from app.validation.answer_checker import AnswerValidator


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
        except Exception as e:
            logger.critical(f"Failed to initialize Orchestrator components: {e}")
            raise

    def process_problem(self, user_input: str, request_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Orchestrates the problem solving pipeline.

        Pipeline:
        1. Validate & Normalize Input
        2. Hash Input
        3. Cache/DB Lookup
        4. Solve (if needed)
        5. Validate Answer
        6. Store & Cache
        7. Return Result

        Args:
            user_input: The raw problem string from the user.
            request_id: Optional UUID for request tracing.

        Returns:
            Dict[str, Any]: The final result including answer, metadata, and status.
        """
        start_time = time.time()
        result = {
            "status": "error",
            "answer": None,
            "error": None,
            "metadata": {
                "request_id": request_id, 
                "stage": "init"
            }
        }

        # 1. Input Processing
        try:
            result["metadata"]["stage"] = "input_processing"
            logger.info(f"[{request_id}] Step 1: Processing input")
            processed_input = self.input_processor.process(user_input)
            
            if not processed_input.is_valid:
                logger.warning(f"[{request_id}] Invalid input: {processed_input.error_message}")
                result["error"] = processed_input.error_message
                return result
            
            # Additional input safety check, we only handle text/latex logic here effectively for now
            if processed_input.input_type not in (InputType.TEXT, InputType.LATEX):
                # Placeholder for image handling logic if we were to implement it
                # For now, treat as text or fail if strictly text required
                pass

        except Exception as e:
            logger.error(f"[{request_id}] Input processing failed: {e}")
            result["error"] = "Internal error during input processing."
            result["metadata"]["error_detail"] = str(e)
            return result

        # 2. Hashing
        try:
            result["metadata"]["stage"] = "hashing"
            logger.info(f"[{request_id}] Step 2: Generating hash")
            # We hash the normalized content
            problem_hash = generate_problem_hash(processed_input.cleaned_content)
            result["metadata"]["hash"] = problem_hash
        except Exception as e:
            logger.error(f"[{request_id}] Hashing failed: {e}")
            result["error"] = "Internal error during hashing."
            result["metadata"]["error_detail"] = str(e)
            return result

        # 3. Memory Lookup (Cache & DB)
        try:
            result["metadata"]["stage"] = "memory_lookup"
            logger.info(f"[{request_id}] Step 3: Checking cache for hash {problem_hash}")
            cached_answer = self.cache_manager.get_cached_answer(problem_hash)
            if cached_answer:
                logger.info(f"[{request_id}] Cache hit!")
                result["status"] = "success"
                result["answer"] = cached_answer
                result["metadata"]["source"] = "cache"
                result["metadata"]["latency"] = time.time() - start_time
                return result

            logger.info(f"[{request_id}] Step 3b: Checking database for hash {problem_hash}")
            db_record = self.db_manager.find_by_hash(problem_hash)
            if db_record and "answer" in db_record:
                logger.info(f"[{request_id}] Database hit!")
                answer_data = db_record["answer"]
                
                # Re-populate cache for future speed
                self.cache_manager.set_cached_answer(problem_hash, answer_data)
                
                result["status"] = "success"
                result["answer"] = answer_data
                result["metadata"]["source"] = "database"
                result["metadata"]["latency"] = time.time() - start_time
                return result

        except Exception as e:
            logger.error(f"[{request_id}] Memory lookup failed: {e}")
            # We continue to solve instead of failing, as memory is optimization
        
        # 4. Reasoning (Gemini)
        try:
            result["metadata"]["stage"] = "reasoning"
            logger.info(f"[{request_id}] Step 4: Solving problem with Gemini")
            # We pass the cleaned content
            generated_solution = self.solver.solve(processed_input.cleaned_content)
        except Exception as e:
            logger.error(f"[{request_id}] Solver failed: {e}")
            result["error"] = "Failed to solve the problem. Please try again later."
            result["metadata"]["error_detail"] = str(e)
            # Capture raw response if it was a parsing error (heuristic check on message)
            if "Failed to parse JSON" in str(e):
                 result["metadata"]["raw_response_snippet"] = str(e)
            return result


        # 5. Validation
        try:
            logger.info("Step 5: Validating answer")
            is_valid, validation_errors = self.validator.validate(
                generated_solution, 
                is_math_problem=(processed_input.input_type == InputType.LATEX or "math" in processed_input.cleaned_content.lower()) # Simple heuristic or rely on processed_input
            )

            if not is_valid:
                logger.warning(f"Validation failed: {validation_errors}")
                result["error"] = f"Generated answer failed validation: {', '.join(validation_errors)}"
                # We do NOT store invalid answers
                return result

        except Exception as e:
            logger.error(f"Validation step failed: {e}")
            result["error"] = "Internal error during answer validation."
            return result

        # 6. Storage & Caching
        try:
            logger.info("Step 6: Storing result")
            
            problem_data = {
                "hash": problem_hash,
                "original_input": user_input,
                "cleaned_content": processed_input.cleaned_content,
                "input_type": processed_input.input_type.value,
            }
            
            # Save to DB
            self.db_manager.save_problem(problem_data, generated_solution)
            
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
