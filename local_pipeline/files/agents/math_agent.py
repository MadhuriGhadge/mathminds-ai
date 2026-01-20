"""
MathAgent: orchestrates generation of SymPy code via LLM, sanitization,
safe execution, and explanation via LLM.

Flow:
1. Build prompt for code generation
2. Ask LLM for code
3. Extract and clean code
4. Sanitize code
5. Execute code safely
6. Ask LLM to explain execution / result
7. Return structured dict
"""
import logging
from typing import Dict, Optional

from core.llm_client import LLMClient
from core.sympy_agent import build_sympy_code_prompt, build_explain_prompt, extract_code_from_response
from core.sanitizer import sanitize, SanitizationError
from core.executor import execute, execute_threaded
from core.config import config

logger = logging.getLogger("mathminds.math_agent")


class MathAgent:
    def __init__(self, model: str = "qwen2.5:3b-instruct-q4_K_M"):
        self.llm = LLMClient(model=model)

    def handle(self, query: str, request_id: Optional[str] = None, timestamp: Optional[str] = None) -> Dict:
        response: Dict = {
            "agent": "math",
            "success": False,
            "code": None,
            "sanitized_code": None,
            "execution_result": None,
            "explanation": None,
            "error": None,
            "meta": {"model": self.llm.model},
        }

        # 1. Build prompt and ask LLM to generate code
        prompt = build_sympy_code_prompt(query)
        try:
            logger.info("Requesting code generation from LLM...")
            llm_text = self.llm.generate_code(prompt, max_tokens=1024, temperature=0.0)
            logger.debug(f"Raw LLM response:\n{llm_text}")
            
            extracted_code = extract_code_from_response(llm_text)
            logger.debug(f"Extracted code:\n{extracted_code}")
            
            response["code"] = extracted_code
            
            if not extracted_code or len(extracted_code.strip()) == 0:
                raise ValueError("LLM returned empty code")
                
        except Exception as e:
            logger.exception("LLM code generation failed: %s", e)
            response["error"] = f"LLM code generation failed: {e}"
            return response

        # 2. Sanitize the generated code
        try:
            logger.info("Sanitizing generated code...")
            sanitized = sanitize(response["code"])
            response["sanitized_code"] = sanitized
            logger.debug(f"Sanitized code:\n{sanitized}")
        except SanitizationError as e:
            logger.error(f"Sanitization failed for code:\n{response['code']}")
            logger.exception("Sanitization error: %s", e)
            response["error"] = f"Sanitization failed: {e}"
            
            # Try to provide helpful feedback
            if "invalid syntax" in str(e).lower():
                response["meta"]["hint"] = "The generated code has syntax errors. This may be a prompt issue."
            
            return response

        # 3. Execute code safely
        try:
            logger.info("Executing sanitized code...")
            
            # Choose execution method based on config
            exec_method = config.get_exec_method()
            logger.debug(f"Using execution method: {exec_method}")
            
            if exec_method == "threading":
                exec_out = execute_threaded(response["sanitized_code"], timeout=config.EXEC_TIMEOUT)
            else:
                exec_out = execute(response["sanitized_code"], timeout=config.EXEC_TIMEOUT)
            
            response["execution_result"] = exec_out.to_dict()
            
            if not exec_out.success:
                logger.warning(f"Execution failed: {exec_out.error}")
            else:
                logger.info(f"Execution successful. Result: {exec_out.result}")
                
        except Exception as e:
            logger.exception("Execution failed: %s", e)
            response["error"] = f"Execution failed: {e}"
            return response

        # 4. Ask LLM to explain the result
        try:
            logger.info("Requesting explanation from LLM...")
            explain_prompt = build_explain_prompt(query, response["sanitized_code"], response["execution_result"])
            explanation = self.llm.generate_text(explain_prompt, max_tokens=512, temperature=0.0)
            response["explanation"] = explanation.strip()
            logger.debug(f"Explanation: {explanation[:100]}...")
        except Exception as e:
            logger.warning("Explanation generation failed: %s", e)
            # Not fatal; attach error but return execution info
            response["explanation"] = None
            response["meta"]["explain_error"] = str(e)

        response["success"] = True
        return response