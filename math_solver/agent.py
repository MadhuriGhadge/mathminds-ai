"""
Orchestrator that implements the execution flow.
FIXED: Added a 'Sanitization' step to handle Markdown-wrapped JSON from Gemini.
"""
import json
import re
from typing import Any, Dict, List
from solver import (
    parse_equations_with_gemini,
    symbolic_solve,
    generate_explanation_with_gemini,
    fallback_gemini_reasoning,
)
from utils import ensure_valid_extraction

def sanitize_llm_json(text: Any) -> str:
    """
    The Missing Piece: Extracts raw JSON from Markdown code blocks.
    """
    if not isinstance(text, str):
        return str(text)
    
    # Regex to find content between ```json and ``` or just ``` and ```
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    
    # If no backticks, just strip whitespace
    return text.strip()

def solve_problem(problem: str) -> Dict[str, Any]:
    """
    Top-level orchestrator.
    """
    # 1️⃣ Extraction Attempt
    # We modify this to handle the case where LLM returns a string with backticks
    extraction = parse_equations_with_gemini(problem)

    # If the extraction is a string (common if JSON parsing failed inside llm.py),
    # we try to rescue it here by sanitizing it.
    if isinstance(extraction, str):
        try:
            sanitized = sanitize_llm_json(extraction)
            extraction = json.loads(sanitized)
        except:
            extraction = {"equations": [], "variables": []}

    # 2️⃣ Logic Gate: Does this look like Math?
    if not ensure_valid_extraction(extraction):
        return _handle_fallback(problem, extraction)

    # 3️⃣ Symbolic Solving (The Authority)
    try:
        equations: List[str] = extraction["equations"]
        variables: List[str] = extraction.get("variables", [])
        
        sympy_solution = symbolic_solve(equations, variables)
        
        explanation = generate_explanation_with_gemini(
            original_problem=problem,
            extracted=extraction,
            sympy_solution=sympy_solution,
        )

        return {
            "mode": "symbolic",
            "equations": equations,
            "solution": sympy_solution,
            "explanation": explanation,
        }

    except Exception:
        # 4️⃣ The Takeover: If SymPy fails, let Gemini reason
        return _handle_fallback(problem, extraction)

def _handle_fallback(problem: str, extraction: Any) -> Dict[str, Any]:
    """
    Packages Gemini's string response into a UI-safe dictionary.
    """
    fallback_text = fallback_gemini_reasoning(problem)
    
    return {
        "mode": "llm_reasoning",
        "equations": extraction.get("equations", []) if isinstance(extraction, dict) else [],
        "solution": {"status": "AI Reasoning", "note": "Solved via linguistic logic"},
        "explanation": fallback_text if isinstance(fallback_text, str) else str(fallback_text),
    }