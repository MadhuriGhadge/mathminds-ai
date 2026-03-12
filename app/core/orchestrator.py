"""
orchestrator.py

BUG FIX — Dead elif branch in the agentic streaming loop silently dropped events.

The original if/elif chain:

    if event["type"] == "thought":        ← catches "thought"
        yield event
    elif event["type"] == "answer":
        full_answer += event["content"]
        yield event
    elif event["type"] in ("thought", "action", "observation"):  ← DEAD — "thought" already caught above
        label = ...
        result_schema["metadata"]["logic_trace"].append(...)
        yield event                       ← "action" and "observation" DO get appended to logic_trace here
    elif event["type"] == "error":
        yield event
    else:
        full_answer += str(event.get("content", ""))             ← BUT "action"/"observation" never reach here
        yield {"type": "answer", ...}

The consequence: "action" and "observation" events were yielded (good), BUT their
content was NEVER appended to result_schema["metadata"]["logic_trace"], so the
final persist_log had empty reasoning. More critically, the order of branches
meant the logic_trace append for "thought" was ALSO skipped — the first branch
caught "thought" and just yielded it without logging it.

This is a correctness bug but NOT the main cause of the blank UI. Documented here
for completeness; the primary fix is in schemas.py (missing request_id on Message)
and in frontend/app.py (sent_to_api=True for assistant messages).
"""

import logging
import time
import hashlib
import json
import re

def _normalize_math(text: str) -> str:
    """Inline replacement for math_renderer.render_math().
    Converts LaTeX delimiters to $...$ / $$...$$ for Streamlit MathJax.
    Gemini 2.5 Flash mostly outputs $...$ already — this catches the rare
    \\(...\\) and \\[...\\] variants and cleans ```math blocks.
    """
    if not text:
        return text
    # Block: \[ ... \] → $$ ... $$
    import re as _re
    text = _re.sub(r'\\\[(.+?)\\\]', r'$$\1$$', text, flags=_re.DOTALL)
    # Inline: \( ... \) → $ ... $
    text = _re.sub(r'\\\((.+?)\\\)', r'$\1$',   text, flags=_re.DOTALL)
    # ```math blocks → $$ ... $$
    text = _re.sub(r'```math\s*(.+?)\s*```', r'$$\1$$', text, flags=_re.DOTALL)
    # Empty $$$$ artifacts
    text = _re.sub(r'\$\$\s*\$\$', '', text)
    return text.strip()

import asyncio
from typing import Any, Dict, Optional, AsyncGenerator

from app.core.input_processor import InputProcessor
from app.core.math_normalizer import MathQueryNormalizer, MathIntent
from app.memory.cache import CacheManager
from app.core.sympy_solver import SymPySolver
from app.memory.semantic_cache import SemanticCache
from app.memory.database import DatabaseManager

from app.core.settings import settings
from app.agents.adk_mathminds import MathMindsADKAgent

logger = logging.getLogger(__name__)


class Orchestrator:
    """
    Evolved Pipeline: Cache → Pre-flight (SymPy) → Agentic Streaming Loop
    """

    def __init__(
        self,
        cache_manager: Optional[CacheManager] = None,
        db_manager: Optional[DatabaseManager] = None,
        semantic_cache: Optional[SemanticCache] = None,
        redis_client: Any = None,
    ):
        try:
            self.input_processor = InputProcessor()
            self.normalizer      = MathQueryNormalizer()
            self.cache_manager   = cache_manager or CacheManager()
            self.db_manager      = db_manager or DatabaseManager()
            self.redis_client    = redis_client
            self.adk_agent       = MathMindsADKAgent(redis_client=self.redis_client)
            self.sympy_solver    = SymPySolver()

            # Semantic cache — use injected instance from deps.py if provided,
            # otherwise create internally.
            if semantic_cache is not None:
                self.semantic_cache = semantic_cache if settings.ENABLE_CACHE else None
            else:
                self.semantic_cache = SemanticCache(
                    redis_client   = self.redis_client,
                    gemini_api_key = settings.GOOGLE_API_KEY,
                ) if settings.ENABLE_CACHE else None
        except Exception as e:
            logger.critical(f"Failed to initialize Orchestrator: {e}")
            raise

    async def solve_problem_stream(
        self,
        query: Optional[str] = None,
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
            "metadata": {
                "latency_ms":  0,
                "model":       "gemini-2.5-flash",
                "tools_used":  [],
                "logic_trace": [],
            },
        }

        try:
            # ── 1. Input processing ───────────────────────────────────────────
            processed = self.input_processor.process_compound(
                text_input=query, image_input=image
            )
            if not processed.is_valid:
                yield {"type": "error", "content": processed.error_message}
                return

            query      = processed.cleaned_content
            image_data = processed.metadata.get("image_data") if processed.metadata else None

            # ── 1.5. Persist user message (idempotent) ────────────────────────
            if user_id and session_id:
                history = self.db_manager.get_chat_history(user_id, session_id) or []
                if not any(m.get("request_id") == request_id for m in history):
                    await self._persist_message(
                        user_id=user_id, session_id=session_id, role="user",
                        content=query or "Uploaded an image", image_data=image_data,
                        request_id=request_id,
                    )

            # ── 2. Cache lookup — two layers ──────────────────────────────────
            #
            # Layer 1 — Exact hash (Redis, microseconds, zero API cost)
            #   sha256(normalized_query) → instant lookup for identical questions
            #
            # Layer 2 — Semantic similarity (Redis embeddings, ~50ms, uses
            #   gemini-embedding-001 which has its OWN 1500 req/day quota,
            #   completely separate from the 20 req/day generate_content limit)
            #   Cosine similarity ≥ 0.85 → treat as same question
            #
            # Both layers are skipped for image queries (can't embed images).
            cache_key      = None
            cached_answer  = None
            cache_source   = None

            if settings.ENABLE_CACHE and not image_data:
                cache_key = self._make_cache_key(query)

                # Layer 1: exact hash
                exact = self.cache_manager.get_cached_answer(cache_key)
                if exact:
                    cached_answer = exact.get("answer")
                    cache_source  = "exact_cache"
                    logger.info(f"Cache layer 1 HIT (exact) for key={cache_key[:8]}")

                # Layer 2: semantic similarity (only if exact missed)
                if not cached_answer and self.semantic_cache:
                    sem = self.semantic_cache.get(query)
                    if sem:
                        cached_answer = sem["answer"]
                        cache_source  = f"semantic_cache (similarity={sem['similarity']}))"
                        logger.info(f"Cache layer 2 HIT (semantic) similarity={sem['similarity']}")

                if cached_answer:
                    yield {"type": "thought", "content": f"💾 Retrieving from memory ({cache_source})..."}
                    yield {"type": "answer",  "content": cached_answer}
                    if user_id and session_id:
                        await self._persist_log(
                            query,
                            {"answer": cached_answer, "metadata": {"source": cache_source}},
                            user_id, session_id, cache_key,
                            request_id=request_id,
                        )
                    return

            # ── 3. SymPy Preflight ────────────────────────────────────────────
            # Try to solve symbolically BEFORE calling Gemini.
            # Cost: 0 LLM calls. Handles derivatives, integrals,
            # equations, limits, arithmetic in milliseconds.
            # If SymPy can't solve it → falls through to Gemini.
            if not image_data:
                math_intent = self.normalizer.normalize(query)
                if math_intent:
                    sympy_result = self.sympy_solver.solve(math_intent)
                    if sympy_result:
                        # sympy_solver.solve() returns a plain str, not a dict
                        answer = sympy_result
                        yield {"type": "thought", "content": f"⚡ Solving symbolically ({math_intent.intent})..."}
                        yield {"type": "answer",  "content": _normalize_math(answer)}
                        result_schema["answer"]          = answer
                        result_schema["metadata"]["source"] = "sympy_preflight"
                        result_schema["metadata"]["intent"] = math_intent.intent
                        if user_id and session_id:
                            await self._persist_log(
                                query, result_schema,
                                user_id, session_id, cache_key,
                                request_id=request_id,
                            )
                        return

            # ── 4. Agentic Streaming Loop ─────────────────────────────────────
            # FIX: The original had a dead elif branch. The chain was:
            #   if "thought" → yield
            #   elif "answer" → accumulate + yield
            #   elif ("thought","action","observation") → log + yield   ← "thought" ALREADY matched above
            #   elif "error" → yield
            #
            # Result: "action" and "observation" were yielded but never logged to
            # logic_trace. Rewritten as explicit branches with no dead code.
            full_answer = ""
            async for event in self.adk_agent.solve(
                problem=query, image_data=image_data,
                session_id=session_id, user_id=user_id,
            ):
                ev_type = event.get("type", "")
                content = event.get("content", "")

                if ev_type == "answer":
                    # Normalize LaTeX and SymPy notation before sending to frontend
                    content     = _normalize_math(content)
                    full_answer += content
                    yield {**event, "content": content}

                elif ev_type == "thought":
                    result_schema["metadata"]["logic_trace"].append(content)
                    yield event

                elif ev_type == "action":
                    result_schema["metadata"]["logic_trace"].append(f"⚙️ {content}")
                    yield event

                elif ev_type == "observation":
                    result_schema["metadata"]["logic_trace"].append(f"👁️ {content}")
                    yield event

                elif ev_type == "error":
                    yield event

                else:
                    # Unexpected event type — treat as answer text so nothing is lost
                    if content:
                        full_answer += str(content)
                        yield {"type": "answer", "content": str(content)}

            # ── 5. Finalize ───────────────────────────────────────────────────
            result_schema["answer"] = full_answer
            result_schema["metadata"]["latency_ms"] = int((time.time() - start_time) * 1000)

            if full_answer:
                await self._persist_log(
                    query, result_schema, user_id, session_id, cache_key,
                    request_id=request_id,
                )

        except Exception as e:
            logger.error(f"Orchestrator Error: {e}", exc_info=True)
            yield {"type": "error", "content": f"Internal Error: {str(e)}"}

    async def solve_problem(
        self,
        query: Optional[str] = None,
        image: Optional[str] = None,
        request_id: Optional[str] = None,
        model_preference: str = "fast",
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Non-streaming version of solve_problem.
        Executes the full agent loop and returns the final answer object.
        """
        full_answer = ""
        logic_trace = []
        error       = None
        
        # We wrap the logic here to ensure we get a consistent response
        # by consuming the stream which already handles persistence.
        async for event in self.solve_problem_stream(
            query=query,
            image=image,
            request_id=request_id,
            model_preference=model_preference,
            session_id=session_id,
            user_id=user_id,
        ):
            ev_type = event.get("type")
            content = event.get("content")
            
            if ev_type == "answer":
                full_answer += content
            elif ev_type in ("thought", "action", "observation"):
                logic_trace.append(content)
            elif ev_type == "error":
                error = content
        
        return {
            "request_id": request_id or "unknown",
            "status":     "error" if error else "success",
            "answer":     full_answer,
            "error":      error,
            "metadata": {
                "logic_trace": logic_trace,
                "timestamp":   time.time(),
            }
        }

    async def _persist_message(self, user_id, session_id, role, content, **kwargs):
        try:
            self.db_manager.create_session(user_id, session_id)
            self.db_manager.save_chat_message(user_id, session_id, role, content, **kwargs)
        except Exception as e:
            logger.error(f"Failed to persist message: {e}")

    async def _persist_log(self, query, schema, user_id, session_id, cache_key, request_id=None):
        reasoning = "\n".join(schema.get("metadata", {}).get("logic_trace", []))
        await self._persist_message(
            user_id=user_id, session_id=session_id, role="assistant",
            content=schema["answer"], reasoning=reasoning,
            metadata=schema.get("metadata", {}),
            request_id=request_id,
        )
        if settings.ENABLE_CACHE and cache_key:
            # Layer 1: exact hash cache
            self.cache_manager.set_cached_answer(cache_key, schema)
            # Layer 2: semantic cache (stores embedding vector alongside answer)
            # Only store if we have a real answer — don't cache errors/empty strings
            # Wrapped in to_thread: semantic_cache.set() calls the embedding API
            # (blocking HTTP). Running it in a thread means the response is already
            # returned to the user before the cache write completes.
            # Skip semantic cache write for SymPy answers — they are deterministic,
            # so caching them via embedding similarity adds no value and wastes
            # 1 embedding API call (out of the 1500/day quota).
            source = schema.get("metadata", {}).get("source", "")
            if self.semantic_cache and schema.get("answer") and source != "sympy_preflight":
                await asyncio.to_thread(
                    self.semantic_cache.set,
                    query    = query,
                    answer   = schema["answer"],
                    metadata = schema.get("metadata", {}),
                )
        # pymongo is sync — run in thread so it doesn't block the event loop
        await asyncio.to_thread(self.db_manager.save_problem, {"content": query}, schema)

    def _make_cache_key(self, query: str) -> str:
        return hashlib.sha256(query.strip().lower().encode()).hexdigest()