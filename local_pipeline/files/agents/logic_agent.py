"""
LogicAgent: simple agent to handle boolean/logic style problems.

For now it delegates to the MathAgent by constructing SymPy logic predicates
where appropriate. This module is written to be extended later with a bespoke
logic solver or SAT engine.
"""
import logging
from typing import Dict, Optional

from core.llm_client import LLMClient
from core.sanitizer import sanitize, SanitizationError
from core.executor import execute
from core.sympy_agent import build_explain_prompt

logger = logging.getLogger("mathminds.logic_agent")


class LogicAgent:
    def __init__(self, model: str = "qwen2.5:3b-instruct-q4_K_M"):
        self.llm = LLMClient(model=model)

    def handle(self, query: str, request_id: Optional[str] = None, timestamp: Optional[str] = None) -> Dict:
        """
        Basic pipeline:
        - Ask the LLM to produce Python code (using sympy.logic or plain Python)
        - Sanitize, execute, and explain similarly to MathAgent
        """
        response = {
            "agent": "logic",
            "success": False,
            "code": None,
            "sanitized_code": None,
            "execution_result": None,
            "explanation": None,
            "error": None,
            "meta": {"model": self.llm.model},
        }

        # Build a simple prompt tailored to logic if the model is capable
        prompt = f"""You are a python expert who solves logic problems. Produce Python code using sympy.logic or plain Python that evaluates the problem. Assign the final answer to 'result'.

Problem:
{query}

Return only Python code."""
        try:
            llm_text = self.llm.generate_code(prompt, max_tokens=1024, temperature=0.0)
            # extract code: simple heuristic
            response["code"] = llm_text.strip()
        except Exception as e:
            logger.exception("LLM generation for logic failed: %s", e)
            response["error"] = str(e)
            return response

        # Sanitize
        try:
            sanitized = sanitize(response["code"])
            response["sanitized_code"] = sanitized
        except SanitizationError as e:
            logger.exception("Sanitization failed: %s", e)
            response["error"] = f"Sanitization failed: {e}"
            return response

        # Execute
        try:
            exec_out = execute(response["sanitized_code"], timeout=6)
            response["execution_result"] = exec_out.to_dict()
        except Exception as e:
            logger.exception("Execution failed: %s", e)
            response["error"] = str(e)
            return response

        # Explain
        try:
            explain_prompt = build_explain_prompt(query, response["sanitized_code"], response["execution_result"])
            explanation = self.llm.generate_text(explain_prompt, max_tokens=512, temperature=0.0)
            response["explanation"] = explanation.strip()
        except Exception as e:
            logger.exception("Explanation failed: %s", e)
            response["meta"]["explain_error"] = str(e)

        response["success"] = True
        return response