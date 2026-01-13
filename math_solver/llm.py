"""
Gemini (LLM) client wrapper.

Responsibilities:
- Interact with the Gemini SDK and provide narrowly-scoped helpers:
  - extract_equations: returns strict JSON (no solving)
  - explain_solution: explains SymPy's provided solution (do NOT recompute)
  - fallback_solve_and_explain: allowed to compute/reason when SymPy fails

This file encapsulates all LLM prompt engineering; callers must not perform LLM prompting themselves.
"""

from typing import Any, Dict
import os
import json
import logging
import re

try:
    from google import genai
except Exception:
    genai = None

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class GeminiClient:
    """
    Minimal wrapper around genai.Client.

    WHY: Isolate all external LLM interaction so the rest of the app remains testable and deterministic.
    """

    def __init__(self) -> None:
        api_key = os.getenv("GENAI_API_KEY", "").strip()
        if not api_key:
            logger.warning("GENAI_API_KEY not set. GeminiClient will raise when used.")
            self._client = None
        elif genai is None:
            logger.warning("google.genai SDK not available in environment.")
            self._client = None
        else:
            try:
                self._client = genai.Client(api_key=api_key)
            except Exception as e:
                logger.exception("Failed to create genai.Client: %s", e)
                self._client = None

    # ---------------------------------------------------------------------
    # Internal generator
    # ---------------------------------------------------------------------

    def _generate(self, prompt: str, max_output_tokens: int = 512, temperature: float = 0.0) -> str:
        if not self._client:
            raise RuntimeError("Gemini client not configured. Set GENAI_API_KEY and install google-genai.")

        try:
            response = self._client.models.generate_content(
                model="gemini-2.0-flash-lite-001",
                contents=prompt,
                config={
                    "max_output_tokens": max_output_tokens,
                    "temperature": temperature,
                },
            )

            if hasattr(response, "text") and response.text:
                return response.text

            if hasattr(response, "candidates") and response.candidates:
                parts = response.candidates[0].content.parts
                return "".join(p.text for p in parts if hasattr(p, "text"))

            return str(response)

        except Exception as e:
            logger.exception("Gemini generation failed: %s", e)
            raise

    # ---------------------------------------------------------------------
    # Utilities
    # ---------------------------------------------------------------------

    @staticmethod
    def sanitize_llm_json(raw_text: str) -> str:
        """
        Extracts the first valid JSON object from messy LLM output.
        Handles markdown blocks and conversational text.
        """
        if not raw_text or not isinstance(raw_text, str):
            return "{}"

        # Try markdown fenced JSON
        markdown_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw_text)
        if markdown_match:
            return markdown_match.group(1).strip()

        # Fallback: extract between first { and last }
        try:
            start = raw_text.index("{")
            end = raw_text.rindex("}") + 1
            return raw_text[start:end].strip()
        except ValueError:
            return "{}"

    # ---------------------------------------------------------------------
    # Equation extraction (STRICT JSON)
    # ---------------------------------------------------------------------

    def extract_equations(self, problem: str) -> Dict[str, Any]:
        prompt = f"""
You are an equation extractor.

Extract all equations and variables from the following natural language math problem.

Rules:
- Output STRICT JSON only.
- No markdown.
- No explanation.
- No solving.
- Keys: "equations" (array of strings), "variables" (array of strings).
- Use SymPy-compatible syntax.
- If nothing can be extracted, return:
  {{ "equations": [], "variables": [] }}

Problem:
\"\"\"{problem}\"\"\"

Example:
{{ "equations": ["x + y = 10"], "variables": ["x", "y"] }}
"""

        raw = self._generate(prompt, max_output_tokens=256, temperature=0)

        try:
            clean = self.sanitize_llm_json(raw)
            parsed = json.loads(clean)

            if not isinstance(parsed, dict):
                raise ValueError("Parsed JSON is not a dictionary")

            return {
                "equations": parsed.get("equations", []),
                "variables": parsed.get("variables", []),
            }

        except Exception:
            logger.exception("Failed to parse Gemini extraction output. Raw output:\n%s", raw)
            return {"equations": [], "variables": []}

    # ---------------------------------------------------------------------
    # Explanation of SymPy solution (NO recomputation)
    # ---------------------------------------------------------------------

    def explain_solution(self, original_problem: str, extracted: Dict[str, Any], sympy_solution: Any) -> str:
        sympy_text = json.dumps(sympy_solution, indent=2)

        prompt = f"""
You are a math tutor.

A symbolic solver (SymPy) already solved the problem.

Your job:
- Explain the provided solution.
- Do NOT recompute.
- Do NOT change values.
- Do NOT introduce new equations.

Original problem:
\"\"\"{original_problem}\"\"\"

Extracted equations:
{json.dumps(extracted, indent=2)}

SymPy solution:
{sympy_text}

Provide a clear step-by-step explanation.

Output plain text only.
"""

        return self._generate(prompt, max_output_tokens=2000, temperature=0)

    # ---------------------------------------------------------------------
    # Fallback logical reasoning solver (LLM takeover)
    # ---------------------------------------------------------------------

    def fallback_solve_and_explain(self, original_problem: str) -> str:
        prompt = f"""
You are a reasoning assistant.

Solve the following problem using clear logical reasoning.

Rules:
- Show steps in natural language.
- Be precise.
- Provide the final answer clearly.
- Do NOT use JSON.
- Do NOT use code blocks.
- Output plain text only.

Problem:
\"\"\"{original_problem}\"\"\"
"""

        try:
            result = self._generate(prompt, max_output_tokens=2000, temperature=0.4)
            return result.strip()
        except Exception as e:
            logger.exception("Gemini fallback reasoning failed: %s", e)
            return "Unable to solve the problem due to an internal error."
