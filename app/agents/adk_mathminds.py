"""
adk_mathminds.py — Google ADK-based MathMinds agent

"""

import logging
import asyncio
import base64
import json
import contextvars
from typing import Optional, AsyncGenerator, Dict, Any

from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.adk.tools.google_search_agent_tool import GoogleSearchAgentTool, create_google_search_agent
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.genai import types
from google import genai
from google.genai.errors import ClientError

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.core.settings import settings
from app.core.llm_guard import check_and_increment
from app.tools.similarity_search import SimilarProblemFinder
from app.tools.python_executor import PythonInterpreter
from app.tools.advanced_ocr import AdvancedOCR
from app.tools.vision_analyzer import VisionAnalyzer
from app.core.math_normalizer import MathQueryNormalizer
from app.agents.prompts import SOLVER_PROMPT, ANALYZER_PROMPT, TUTOR_PROMPT

logger = logging.getLogger(__name__)

# Context var carries image data into tool functions without passing it as an argument
current_image_ctx: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "current_image", default=None
)

_QUOTA_MESSAGE = (
    "⚠️ Daily question limit reached. Please try again tomorrow, "
    "or ask your administrator to increase the quota."
)


class MathMindsADKAgent:

    def __init__(self, model_name: str = "gemini-2.5-flash", agent_mode: str = "solver", redis_client=None):

        self.api_key      = settings.GOOGLE_API_KEY
        self.redis_client = redis_client
        self._model_name  = model_name
        self._agent_mode  = agent_mode.lower()

        if not self.api_key:
            logger.warning("No Google API Key found.")

        self.genai_client = genai.Client(api_key=self.api_key)

        # ── Sub-tools ─────────────────────────────────────────────────────
        self.normalizer      = MathQueryNormalizer()
        self.similar_finder  = SimilarProblemFinder()
        self.python_executor = PythonInterpreter()
        self.advanced_ocr    = AdvancedOCR()
        self.vision_analyzer = VisionAnalyzer()

        # Pre-warm TrOCR at startup — first image request otherwise takes 60s
        # to download and load the model weights from HuggingFace.
        # load_model() is idempotent (checks self.model is None before loading).
        try:
            self.advanced_ocr.load_model()
        except Exception as e:
            logger.warning(f"TrOCR pre-warm failed (image OCR will lazy-load): {e}")

        # ── Session service — created ONCE here, not inside _get_agent() ──
        self.session_service = InMemorySessionService()

        # ── Multi-Agent Search: Sub-agent with native grounding ────────────
        self.search_sub_agent = create_google_search_agent(model=self._model_name)
        self.web_search_tool  = GoogleSearchAgentTool(agent=self.search_sub_agent)

        # ── Tool definitions ───────────────────────────────────────────────
        async def run_with_timeout(coro, timeout=20):
            try:
                return await asyncio.wait_for(coro, timeout)
            except asyncio.TimeoutError:
                return "Tool timed out."

        # web_search: uses google_search grounding built into the agent
        # (NOT a separate generate_content call — costs zero extra quota)
        # web_search: provided via GoogleSearchAgentTool sub-agent
        # to avoid Mixing Grounding + Function Calling conflict
        web_search = self.web_search_tool

        @retry(
            stop=stop_after_attempt(2),
            wait=wait_exponential(multiplier=1, min=2, max=5),
            retry=retry_if_exception_type(Exception),
        )
        async def execute_python(reasoning: str, code: str) -> str:
            """Execute Python code and return the result.
            
            Args:
                reasoning: Step-by-step mathematical reasoning for why this code is being executed.
                code: The Python code to execute.
            """
            result = await run_with_timeout(
                self.python_executor.execute(code), timeout=15
            )
            if isinstance(result, str):
                return result
            if result.get("status") == "success":
                return f"Output:\n{result.get('content')}\nResult: {result.get('result')}"
            return f"Python execution error: {result.get('content')}"

        async def image_interpreter() -> str:
            """Extract text and equations from the uploaded image using OCR."""
            image_data = current_image_ctx.get()
            if not image_data:
                return "Error: No image provided."
            try:
                if "," in image_data:
                    image_data = image_data.split(",")[1]
                img_bytes = base64.b64decode(image_data)
                if len(img_bytes) > 5_000_000:
                    return "Image too large. Please upload a smaller image."
                text = self.advanced_ocr.process_image_bytes(img_bytes)
                return f"OCR result (LaTeX/Text): {text}" if text else "OCR failed to detect text."
            except Exception as e:
                return f"OCR error: {e}"

        async def statistical_vision(query: str) -> str:
            """Analyze objects and quantities in the uploaded image."""
            image_data = current_image_ctx.get()
            if not image_data:
                return "Error: No image provided."
            result = self.vision_analyzer.analyze(image_data, query)
            if result.get("status") == "success":
                quant = result.get("quantitative_analysis")
                if quant:
                    return (
                        f"Vision Analysis: Found {quant.get('total_objects')} objects. "
                        f"Details: {quant.get('objects')}"
                    )
                return "Vision analysis found no objects."
            return f"Vision analysis error: {result.get('error')}"

        async def find_similar_problems(query: str) -> str:
            """Find similar previously solved math problems."""
            results = self.similar_finder.search(query, limit=2)
            if not results:
                return "No similar problems found."
            formatted = "Similar problems:\n"
            for item in results:
                formatted += (
                    f"Problem: {item.get('problem_text')}\n"
                    f"Solution: {item.get('solution_text')}\n---\n"
                )
            return formatted

        # ── Tool registry ──────────────────────────────────────────────────
        self.tools = {
            "web_search":           web_search,
            "execute_python":       execute_python,
            "find_similar_problems":find_similar_problems,
            "image_interpreter":    image_interpreter,
            "statistical_vision":   statistical_vision,
        }

        # ── Pre-build both agent variants and their runners ────────────────
        # Runner is heavy — creating it once here avoids rebuilding on every
        # solve() call (previous version rebuilt it on every request)
        self._runner_text  = self._build_runner(has_image=False)
        self._runner_image = self._build_runner(has_image=True)

        logger.info(f"MathMindsADKAgent initialized with model: {model_name}")

    # ── Agent / Runner builders ────────────────────────────────────────────

    def _build_agent(self, has_image: bool) -> Agent:
        active_tools = [
            self.tools["web_search"],
            self.tools["find_similar_problems"],
        ]
        if has_image:
            active_tools.append(self.tools["image_interpreter"])
            active_tools.append(self.tools["statistical_vision"])

        return Agent(
            name="math_minds_core",
            model=self._model_name,
            tools=active_tools,
            # google_search grounding is REMOVED here to avoid 400 Bad Request conflict.
            # grounding is now provided by the web_search sub-agent tool.
            generate_content_config=types.GenerateContentConfig(
                temperature=0.1 if self._agent_mode in ["solver", "analyzer"] else 0.4,
            ),
            instruction=ANALYZER_PROMPT if self._agent_mode == "analyzer" else (TUTOR_PROMPT if self._agent_mode == "tutor" else SOLVER_PROMPT),
        )

    def _build_runner(self, has_image: bool) -> Runner:
        return Runner(
            app_name="mathminds",
            agent=self._build_agent(has_image=has_image),
            session_service=self.session_service,
        )

    # ── Main solve method ──────────────────────────────────────────────────

    def _get_image_mime(self, data_bytes: bytes) -> str:
        """Fallback for imghdr in Python 3.13+"""
        if data_bytes.startswith(b'\xff\xd8\xff'):
            return "image/jpeg"
        if data_bytes.startswith(b'\x89PNG\r\n\x1a\n'):
            return "image/png"
        if data_bytes.startswith(b'GIF87a') or data_bytes.startswith(b'GIF89a'):
            return "image/gif"
        if data_bytes.startswith(b'RIFF') and data_bytes[8:12] == b'WEBP':
            return "image/webp"
        return "image/unknown"

    async def solve(
        self,
        problem: str,
        image_data: Optional[str] = None,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        chat_history: Optional[list] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:

        token = current_image_ctx.set(image_data)

        try:
            # Normalize query (cleans up math notation)
            # NOTE: problem may already be normalized if coming from orchestrator.py
            # but normalize() is idempotent for strings.
            norm_res = self.normalizer.normalize(str(problem))
            if norm_res:
                 # If it returned a MathIntent object, convert to string for GenAI Parts
                 problem = f"{norm_res.intent}: {norm_res.expression}"
            
            # Quota check
            if self.redis_client:
                allowed, used, limit = check_and_increment(self.redis_client, user_id)
                if not allowed:
                    # llm_guard already logged the warning — no need to repeat it
                    yield {"type": "error", "content": _QUOTA_MESSAGE}
                    return
                # llm_guard already logs "LLM quota used" — no duplicate log here

            # We bypass the volatile InMemorySessionService and directly inject 
            # MongoDB's persistent chat_history into the prompt for perfect memory.
            if chat_history:
                recent_history = chat_history[-10:]
                history_text = "=== PAST CONVERSATION: ===\n"
                for msg in recent_history:
                    r = "User" if msg.get("role") == "user" else "Assistant"
                    history_text += f"{r}:\n{msg.get('content', '')}\n\n"
                history_text += "=== CURRENT REQUEST: ===\n"
                problem = f"{history_text}{problem}"

            # Build message parts
            parts = [types.Part.from_text(text=str(problem) or "Analyze this image.")]

            # We must pass a session_id to ADK, but we want to ignore ADK's tracking 
            # to prevent duplicate history (since we use MongoDB). 
            # Solution: Create a disposable single-turn session!
            import uuid
            stateless_id = f"single_turn_{uuid.uuid4().hex}"
            try:
                await self.session_service.create_session(
                    app_name="mathminds", user_id=user_id, session_id=stateless_id
                )
            except Exception:
                pass

            if image_data:
                try:
                    img_bytes = base64.b64decode(image_data)
                    
                    # ── YOLO VISUAL PIPELINE ──
                    if not hasattr(self, 'yolo_analyzer'):
                        from app.tools.yolo_vision import YoloVisionAnalyzer
                        self.yolo_analyzer = YoloVisionAnalyzer()
                        
                    logger.info("Running YOLO inference...")
                    yolo_result = self.yolo_analyzer.process_image(img_bytes)
                    
                    if yolo_result.get("status") == "success" and yolo_result.get("annotated_base64"):
                        # Log bounding box data to Logic Trace
                        yield {"type": "observation", "content": f"YOLOv8 detected {yolo_result.get('object_count')} object regions."}
                        
                        # Embed the drawn bounding boxes immediately in the UI text stream
                        b64 = yolo_result["annotated_base64"]
                        yield {"type": "answer", "content": f"\n\n**YOLO Vision Framing:**\n\n![Visual](data:image/png;base64,{b64})\n\n---\n\n"}
                        
                        # Give Gemini the heavily-annotated image too
                        img_bytes = base64.b64decode(b64)
                        
                    mime_type = self._get_image_mime(img_bytes)
                    parts.append(types.Part.from_bytes(data=img_bytes, mime_type=mime_type))
                except Exception as e:
                    logger.error(f"Image decode or YOLO failed: {e}")

            # Pick the pre-built runner for this request type
            runner = self._runner_image if image_data else self._runner_text

            # ── Streaming loop ─────────────────────────────────────────────
            # FIX: yield ONLY from is_final_response() events.
            #
            # ADK SSE behaviour:
            #   Intermediate events → contain raw cumulative text fragments
            #   Final event (is_final_response()==True) → contains the complete answer
            #
            # Old code used a cursor (yielded_text_len) to slice deltas from every
            # event. This caused garbling because fragments aren't always contiguous,
            # and the final event re-sent the full text causing duplication.
            _seen_tool_calls: set = set()
            _last_text: str = ""  # fallback: track last non-empty text seen

            async for event in runner.run_async(
                user_id=user_id,
                session_id=stateless_id,
                new_message=types.Content(role="user", parts=parts),
                run_config=RunConfig(streaming_mode=StreamingMode.SSE),
            ):
                # Check is_final safely (method may not exist on all event types)
                try:
                    is_final = event.is_final_response()
                except Exception:
                    is_final = False

                # Extract text from this event's parts (if any)
                event_text = ""
                if hasattr(event, "content") and event.content and event.content.parts:
                    event_text = "".join(
                        (getattr(p, "text", "") or "") for p in event.content.parts
                    )
                if event_text:
                    _last_text = event_text

                # Yield answer only from final event.
                # If the final event has no text (e.g. function_response parts only),
                # fall back to the last non-empty text we saw — this handles the
                # statistical_vision case where ADK's final event contains only
                # tool result parts and the actual Gemini text is in a prior event.
                if is_final:
                    answer = event_text or _last_text
                    if answer:
                        yield {"type": "answer", "content": answer}

                # Tool calls — deduplicated by name only.
                # ADK emits the same function_call in multiple events (request +
                # response context) with DIFFERENT fc.id values each time, so
                # keying on id doesn't deduplicate. Name-only dedup is safe because
                # within a single turn Gemini won't call the same tool twice.
                for fc in event.get_function_calls():
                    # Dedup by name + args to allow same tool later with different args
                    # Hashable representation of the call for dedup
                    call_hash = f"{fc.name}:{hash(str(getattr(fc, 'args', '')))}"
                    if call_hash not in _seen_tool_calls:
                        _seen_tool_calls.add(call_hash)
                        logger.info(f"Tool called: {fc.name}")
                        yield {"type": "action", "content": fc.name}
                        
                        # Extract reasoning if it exists in args
                        if hasattr(fc, "args") and isinstance(fc.args, dict) and "reasoning" in fc.args:
                            yield {"type": "thought", "content": f"🤔 {fc.args['reasoning']}"}

                for fr in event.get_function_responses():
                    logger.info(f"Tool response: {fr.name}")
                    yield {"type": "observation", "content": fr.name}

        except ClientError as e:
            err = str(e).lower()
            if "429" in err or "resource_exhausted" in err or "quota" in err:
                logger.warning(f"Gemini quota/rate error: {e}")
                yield {"type": "error", "content": _QUOTA_MESSAGE}
            else:
                logger.error(f"Gemini ClientError: {e}")
                yield {"type": "error", "content": "The AI service returned an error. Please try again."}

        except Exception as e:
            err = str(e).lower()
            if "429" in err or "quota" in err or "resource_exhausted" in err:
                logger.warning(f"Quota error (generic): {e}")
                yield {"type": "error", "content": _QUOTA_MESSAGE}
            else:
                logger.error(f"Agent execution failed: {e}", exc_info=True)
                yield {"type": "error", "content": "Something went wrong. Please try again."}

        finally:
            try:
                current_image_ctx.reset(token)
            except ValueError as exc:
                if "was created in a different" not in str(exc):
                    raise