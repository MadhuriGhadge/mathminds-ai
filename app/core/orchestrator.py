import logging
import time
import hashlib
import json
import re
from typing import Any, Dict, Optional

import sympy
from sympy.parsing.sympy_parser import parse_expr, standard_transformations, implicit_multiplication_application

from app.core.input_processor import InputProcessor
from app.core.math_normalizer import MathQueryNormalizer, MathIntent
from app.memory.cache import CacheManager
from app.memory.database import DatabaseManager
from app.agents.adk_mathminds import MathMindsADKAgent
from app.core.settings import settings

logger = logging.getLogger(__name__)

# Transformations that allow "2x" → "2*x" in SymPy
_SYMPY_TRANSFORMATIONS = standard_transformations + (implicit_multiplication_application,)


class Orchestrator:
    """
    Pipeline: Cache → Pre-flight (SymPy) → ADK Agent

    Pre-flight layer solves arithmetic, algebra, derivatives, integrals, and
    equations locally with SymPy — ZERO LLM calls. Only queries that cannot
    be resolved symbolically are forwarded to the ADK Agent.

    With a 20 RPD quota this means:
      - Simple math  → instant, free, no quota used
      - Complex math → ADK agent, 1-2 LLM calls as needed
    """

    def __init__(
        self,
        cache_manager: Optional[CacheManager] = None,
        db_manager: Optional[DatabaseManager] = None,
        redis_client: Any = None,
    ):
        try:
            self.input_processor = InputProcessor()
            self.normalizer      = MathQueryNormalizer()
            self.cache_manager   = cache_manager or CacheManager()
            self.db_manager      = db_manager or DatabaseManager()
            self.redis_client    = redis_client
            self.adk_agent       = MathMindsADKAgent(redis_client=self.redis_client)
        except Exception as e:
            logger.critical(f"Failed to initialize Orchestrator: {e}")
            raise

    # ──────────────────────────────────────────────────────────────────────────
    # Public entry point
    # ──────────────────────────────────────────────────────────────────────────
    async def process_problem(
        self,
        text: Optional[str] = None,
        image: Optional[str] = None,
        request_id: Optional[str] = None,
        model_preference: str = "fast",
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:

        start_time = time.time()
        request_id = request_id or "unknown"

        result_schema: Dict[str, Any] = {
            "request_id": request_id,
            "status":     "error",
            "source":     "google_adk_agent",
            "answer":     None,
            "steps":      [],
            "explanation": None,
            "confidence": 0.0,
            "cached":     False,
            "metadata":   {"latency_ms": 0, "model": "sympy_preflight", "tools_used": []},
        }

        try:
            # ── Step 1: Input processing ───────────────────────────────────────
            processed = self.input_processor.process_compound(text_input=text, image_input=image)
            if not processed.is_valid:
                result_schema["explanation"] = processed.error_message
                return self._finalize(result_schema, start_time)

            query        = processed.cleaned_content
            image_data   = processed.metadata.get("image_data")

            # ── Step 2: Cache lookup ───────────────────────────────────────────
            if settings.ENABLE_CACHE and not image_data:
                cache_key    = self._make_cache_key(query)
                cached       = self.cache_manager.get_cached_answer(cache_key)
                if cached:
                    logger.info(f"Cache hit for query: {query[:60]}")
                    cached["cached"] = True
                    cached["request_id"] = request_id
                    return self._finalize(cached, start_time)
            else:
                cache_key = None

            # ── Step 3: Pre-flight — try SymPy before touching the LLM ────────
            # Only attempted when there is no image (images need vision model).
            if not image_data:
                preflight_result = self._try_sympy(query)
                if preflight_result is not None:
                    result_schema.update({
                        "status":      "success",
                        "source":      "sympy_preflight",
                        "answer":      preflight_result,
                        "explanation": "Solved locally by SymPy — no LLM call needed.",
                        "confidence":  1.0,
                        "metadata":    {"latency_ms": 0, "model": "sympy_preflight", "tools_used": ["sympy"]},
                    })
                    logger.info(f"Pre-flight solved: {query[:60]} → {preflight_result[:80]}")

                    # Cache and persist
                    if settings.ENABLE_CACHE and cache_key:
                        self.cache_manager.set_cached_answer(cache_key, result_schema)
                    self.db_manager.save_problem({"content": query}, result_schema)
                    return self._finalize(result_schema, start_time)

            # ── Step 4: ADK Agent (LLM) ────────────────────────────────────────
            logger.info("Pre-flight could not solve — routing to ADK Agent")
            result_schema["metadata"]["model"] = "gemini-flash-adk"

            try:
                agent_response = await self.adk_agent.solve(
                    problem=query,
                    image_data=image_data,
                    session_id=session_id or "default_session",
                    user_id=user_id,
                )
                result_schema.update({
                    "status":      "success",
                    "source":      "google_adk_agent",
                    "answer":      agent_response,
                    "explanation": "Processed by MathMinds ADK Agent.",
                    "confidence":  1.0,
                })
            except Exception as e:
                logger.error(f"ADK Agent execution failed: {e}")
                result_schema["explanation"] = f"Agent Error: {str(e)}"
                return self._finalize(result_schema, start_time)

            # ── Step 5: Persist ────────────────────────────────────────────────
            if result_schema["status"] == "success":
                if settings.ENABLE_CACHE and cache_key:
                    self.cache_manager.set_cached_answer(cache_key, result_schema)
                self.db_manager.save_problem({"content": query}, result_schema)

            return self._finalize(result_schema, start_time)

        except Exception as e:
            logger.error(f"Orchestrator Critical Error: {e}")
            result_schema["explanation"] = f"Internal Error: {str(e)}"
            return self._finalize(result_schema, start_time)

    # ──────────────────────────────────────────────────────────────────────────
    # Pre-flight: pure SymPy resolution, no LLM
    # ──────────────────────────────────────────────────────────────────────────
    def _try_sympy(self, query: str) -> Optional[str]:
        """
        Attempt to solve the query with the MathQueryNormalizer + SymPy.
        Returns a human-readable answer string, or None if it can't be solved
        locally (which means the ADK Agent should handle it).
        """
        try:
            intent: Optional[MathIntent] = self.normalizer.normalize(query)
            if intent is None:
                return None

            expr_str    = self._prep_expr(intent.expression)
            target_var  = sympy.Symbol(intent.variable or "x")

            if intent.intent == "arithmetic":
                return self._solve_arithmetic(expr_str)

            if intent.intent == "equation":
                return self._solve_equation(expr_str, target_var)

            if intent.intent == "derivative":
                expr   = parse_expr(expr_str, transformations=_SYMPY_TRANSFORMATIONS)
                result = sympy.diff(expr, target_var)
                return f"d/d{target_var}({intent.expression}) = {sympy.latex(result)}"

            if intent.intent == "integral":
                expr   = parse_expr(expr_str, transformations=_SYMPY_TRANSFORMATIONS)
                result = sympy.integrate(expr, target_var)
                return f"∫({intent.expression}) d{target_var} = {sympy.latex(result)} + C"

            if intent.intent == "limit":
                return self._solve_limit(intent, query)

            if intent.intent == "simplification":
                expr   = parse_expr(expr_str, transformations=_SYMPY_TRANSFORMATIONS)
                result = sympy.simplify(expr)
                return f"Simplified: {sympy.latex(result)}"

        except Exception as e:
            # Any parse/evaluation error → fall through to agent
            logger.debug(f"Pre-flight SymPy failed for '{query}': {e}")

        return None

    def _prep_expr(self, expr: str) -> str:
        """Normalise expression string for SymPy."""
        expr = expr.replace("^", "**")                       # ^ → **
        expr = re.sub(r"(\d)([a-zA-Z])", r"\1*\2", expr)    # 2x → 2*x
        expr = re.sub(r"\)\s*\(", ")*(", expr)               # )( → )*(
        return expr.strip()

    def _solve_arithmetic(self, expr_str: str) -> Optional[str]:
        """Evaluate a pure arithmetic/algebraic expression."""
        try:
            expr   = parse_expr(expr_str, transformations=_SYMPY_TRANSFORMATIONS)
            result = sympy.simplify(expr)
            # If the result is a number, show it plainly; otherwise use LaTeX
            if result.is_number:
                numeric = float(result)
                # Show as integer if it is one
                if numeric == int(numeric):
                    return str(int(numeric))
                return f"{numeric:.6g}"
            return sympy.latex(result)
        except Exception:
            return None

    def _solve_equation(self, expr_str: str, var: sympy.Symbol) -> Optional[str]:
        """Solve an equation of the form lhs = rhs, or expr = 0."""
        try:
            parts = expr_str.split("=", 1)
            if len(parts) == 2:
                lhs      = parse_expr(self._prep_expr(parts[0]), transformations=_SYMPY_TRANSFORMATIONS)
                rhs      = parse_expr(self._prep_expr(parts[1]), transformations=_SYMPY_TRANSFORMATIONS)
                solution = sympy.solve(lhs - rhs, var)
            else:
                expr     = parse_expr(expr_str, transformations=_SYMPY_TRANSFORMATIONS)
                solution = sympy.solve(expr, var)

            if not solution:
                return "No solution found."
            if len(solution) == 1:
                return f"{var} = {sympy.latex(solution[0])}"
            sols = ", ".join(sympy.latex(s) for s in solution)
            return f"{var} ∈ {{{sols}}}"
        except Exception:
            return None

    def _solve_limit(self, intent: MathIntent, original_query: str) -> Optional[str]:
        """Parse and evaluate a limit expression."""
        try:
            # Limit pattern: "limit of X as Y approaches Z"
            match = re.search(
                r"limit of\s+(.+?)\s+as\s+(\w+)\s+approaches\s+(.+)",
                original_query, re.IGNORECASE
            )
            if not match:
                return None
            expr_raw  = self._prep_expr(match.group(1))
            var_name  = match.group(2).strip()
            point_raw = self._prep_expr(match.group(3).strip())

            expr  = parse_expr(expr_raw, transformations=_SYMPY_TRANSFORMATIONS)
            var   = sympy.Symbol(var_name)
            point = parse_expr(point_raw, transformations=_SYMPY_TRANSFORMATIONS)

            result = sympy.limit(expr, var, point)
            return f"lim({var}→{point}) {sympy.latex(expr)} = {sympy.latex(result)}"
        except Exception:
            return None

    # ──────────────────────────────────────────────────────────────────────────
    # Utilities
    # ──────────────────────────────────────────────────────────────────────────
    def _make_cache_key(self, query: str) -> str:
        return hashlib.sha256(query.strip().lower().encode()).hexdigest()

    def _finalize(self, schema: Dict, start_time: float) -> Dict:
        schema["metadata"]["latency_ms"] = int((time.time() - start_time) * 1000)
        return schema