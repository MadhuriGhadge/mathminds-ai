import logging
import time
import hashlib
import json
import re
import asyncio
from typing import Any, Dict, Optional, AsyncGenerator

import sympy
from sympy.parsing.sympy_parser import parse_expr, standard_transformations, implicit_multiplication_application

from app.core.input_processor import InputProcessor
from app.core.math_normalizer import MathQueryNormalizer, MathIntent
from app.memory.cache import CacheManager
from app.memory.database import DatabaseManager
from app.agents.adk_mathminds import MathMindsADKAgent
from app.core.settings import settings

logger = logging.getLogger(__name__)

_SYMPY_TRANSFORMATIONS = standard_transformations + (implicit_multiplication_application,)


class Orchestrator:
    """
    Evolved Pipeline: Cache → Pre-flight (SymPy) → Agentic Streaming Loop
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

    async def process_problem(
        self,
        text: Optional[str] = None,
        image: Optional[str] = None,
        request_id: Optional[str] = None,
        model_preference: str = "fast",
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:

        start_time = time.time()
        request_id = request_id or "unknown"

        result_schema: Dict[str, Any] = {
            "request_id": request_id,
            "status":     "success",
            "source":     "agent",
            "answer":     "",
            "metadata":   {"latency_ms": 0, "model": "gemini-2.5-flash", "tools_used": []},
        }

        try:
            # ── 1. Input processing ───────────────────────────────────────────
            processed = self.input_processor.process_compound(text_input=text, image_input=image)
            if not processed.is_valid:
                yield {"type": "error", "content": processed.error_message}
                return

            query = processed.cleaned_content
            image_data = processed.metadata.get("image_data")

            # Background: Persist user message
            if user_id and session_id:
                asyncio.create_task(self._persist_message(
                    user_id=user_id, session_id=session_id, role="user", 
                    content=text or "Uploaded an image", image_data=image_data
                ))

            # ── 2. Cache lookup ───────────────────────────────────────────────
            if settings.ENABLE_CACHE and not image_data:
                cache_key = self._make_cache_key(query)
                cached = self.cache_manager.get_cached_answer(cache_key)
                if cached:
                    yield {"type": "thought", "content": "Retrieving answer from memory..."}
                    yield {"type": "answer", "content": cached.get("answer")}
                    # Background: Persist assistant response
                    if user_id and session_id:
                        asyncio.create_task(self._persist_message(
                            user_id=user_id, session_id=session_id, role="assistant",
                            content=cached.get("answer"), metadata=cached.get("metadata")
                        ))
                    return
            else:
                cache_key = None

            # ── 3. Pre-flight (SymPy) ─────────────────────────────────────────
            if not image_data:
                preflight_result = self._try_sympy(query)
                if preflight_result is not None:
                    yield {"type": "thought", "content": "Calculating result symbolically..."}
                    yield {"type": "answer", "content": preflight_result}
                    
                    result_schema.update({
                        "source": "sympy_preflight",
                        "answer": preflight_result,
                        "metadata": {"model": "sympy", "tools_used": ["sympy"]}
                    })
                    
                    self._fire_and_forget_log(query, result_schema, user_id, session_id, cache_key)
                    return

            # ── 4. Agentic Streaming Loop ─────────────────────────────────────
            full_answer = ""
            async for event in self.adk_agent.solve(
                problem=query, image_data=image_data, 
                session_id=session_id, user_id=user_id
            ):
                if event["type"] == "thought":
                    yield event
                elif event["type"] == "answer":
                    full_answer += event["content"]
                    yield event
                elif event["type"] in ("thought", "action", "observation"):
                    label = ""
                    if event["type"] == "action": label = "⚙️ "
                    elif event["type"] == "observation": label = "👁️ "
                    
                    result_schema["metadata"]["logic_trace"].append(f"{label}{event['content']}")
                    yield event
                elif event["type"] == "error":
                    yield event
                else:
                    # Fallback for any other content
                    full_answer += str(event.get("content", ""))
                    yield {"type": "answer", "content": str(event.get("content", ""))}

            # ── 5. Finalize ───────────────────────────────────────────────────
            result_schema["answer"] = full_answer
            result_schema["metadata"]["latency_ms"] = int((time.time() - start_time) * 1000)
            
            if full_answer:
                self._fire_and_forget_log(query, result_schema, user_id, session_id, cache_key)

        except Exception as e:
            logger.error(f"Orchestrator Error: {e}")
            yield {"type": "error", "content": f"Internal Error: {str(e)}"}

    async def _persist_message(self, user_id, session_id, role, content, **kwargs):
        try:
            self.db_manager.create_session(user_id, session_id)
            self.db_manager.save_chat_message(user_id, session_id, role, content, **kwargs)
        except Exception as e:
            logger.error(f"Failed to persist message: {e}")

    def _fire_and_forget_log(self, query, schema, user_id, session_id, cache_key):
        """Fire and forget persistence to avoid blocking the stream completion."""
        asyncio.create_task(self._persist_log(query, schema, user_id, session_id, cache_key))

    async def _persist_log(self, query, schema, user_id, session_id, cache_key):
        """Internal awaitable helper."""
        # Map logic_trace to reasoning for frontend consistency
        reasoning = "\n".join(schema["metadata"].get("logic_trace", []))
        
        await self._persist_message(
            user_id=user_id, session_id=session_id, role="assistant",
            content=schema["answer"], reasoning=reasoning, metadata=schema["metadata"]
        )
        if settings.ENABLE_CACHE and cache_key:
            self.cache_manager.set_cached_answer(cache_key, schema)
        self.db_manager.save_problem({"content": query}, schema)

    def _try_sympy(self, query: str) -> Optional[str]:
        try:
            intent: Optional[MathIntent] = self.normalizer.normalize(query)
            if intent is None: return None
            expr_str = self._prep_expr(intent.expression)
            target_var = sympy.Symbol(intent.variable or "x")
            if intent.intent == "arithmetic": return self._solve_arithmetic(expr_str)
            if intent.intent == "equation": return self._solve_equation(expr_str, target_var)
            if intent.intent == "derivative":
                expr = parse_expr(expr_str, transformations=_SYMPY_TRANSFORMATIONS)
                return f"d/d{target_var}({intent.expression}) = {sympy.latex(sympy.diff(expr, target_var))}"
            if intent.intent == "integral":
                expr = parse_expr(expr_str, transformations=_SYMPY_TRANSFORMATIONS)
                return f"∫({intent.expression}) d{target_var} = {sympy.latex(sympy.integrate(expr, target_var))} + C"
            if intent.intent == "limit": return self._solve_limit(intent, query)
            if intent.intent == "simplification":
                expr = parse_expr(expr_str, transformations=_SYMPY_TRANSFORMATIONS)
                return f"Simplified: {sympy.latex(sympy.simplify(expr))}"
        except Exception: pass
        return None

    def _prep_expr(self, expr: str) -> str:
        expr = expr.replace("^", "**")
        expr = re.sub(r"(\d)([a-zA-Z])", r"\1*\2", expr)
        expr = re.sub(r"\)\s*\(", ")*(", expr)
        return expr.strip()

    def _solve_arithmetic(self, expr_str: str) -> Optional[str]:
        try:
            result = sympy.simplify(parse_expr(expr_str, transformations=_SYMPY_TRANSFORMATIONS))
            if result.is_number:
                numeric = float(result)
                return str(int(numeric)) if numeric == int(numeric) else f"{numeric:.6g}"
            return sympy.latex(result)
        except Exception: return None

    def _solve_equation(self, expr_str: str, var: sympy.Symbol) -> Optional[str]:
        try:
            parts = expr_str.split("=", 1)
            if len(parts) == 2:
                lhs = parse_expr(self._prep_expr(parts[0]), transformations=_SYMPY_TRANSFORMATIONS)
                rhs = parse_expr(self._prep_expr(parts[1]), transformations=_SYMPY_TRANSFORMATIONS)
                solution = sympy.solve(lhs - rhs, var)
            else:
                solution = sympy.solve(parse_expr(expr_str, transformations=_SYMPY_TRANSFORMATIONS), var)
            if not solution: return "No solution found."
            if len(solution) == 1: return f"{var} = {sympy.latex(solution[0])}"
            return f"{var} ∈ {{{', '.join(sympy.latex(s) for s in solution)}}}"
        except Exception: return None

    def _solve_limit(self, intent: MathIntent, original_query: str) -> Optional[str]:
        try:
            match = re.search(r"limit of\s+(.+?)\s+as\s+(\w+)\s+approaches\s+(.+)", original_query, re.IGNORECASE)
            if not match: return None
            expr = parse_expr(self._prep_expr(match.group(1)), transformations=_SYMPY_TRANSFORMATIONS)
            var = sympy.Symbol(match.group(2).strip())
            point = parse_expr(self._prep_expr(match.group(3).strip()), transformations=_SYMPY_TRANSFORMATIONS)
            return f"lim({var}→{point}) {sympy.latex(expr)} = {sympy.latex(sympy.limit(expr, var, point))}"
        except Exception: return None

    def _make_cache_key(self, query: str) -> str:
        return hashlib.sha256(query.strip().lower().encode()).hexdigest()
