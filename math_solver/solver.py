"""
Math logic connecting Gemini (LLM) and SymPy.

Responsibilities:
- Ask Gemini to extract equations (NO solving).
- Use SymPy for all symbolic solving.
- Ask Gemini to explain SymPy results (without recomputing).
- Provide a Gemini-only fallback reasoning function when needed.

Strict separation maintained: Gemini never overrides SymPy.
"""
from typing import Any, Dict, List, Optional
import json

from sympy import symbols, sympify, solve, Eq, Symbol
from sympy.core.sympify import SympifyError

from llm import GeminiClient


# Create a shared Gemini client instance.
_gemini = GeminiClient()


def parse_equations_with_gemini(problem: str) -> Dict[str, Any]:
    """
    Ask Gemini to extract equations and variables from natural language.

    Output MUST be strict JSON:
    {
      "equations": ["x + y = 10"],
      "variables": ["x", "y"]
    }

    This function does NOT perform any solving.
    """
    # Delegate to the Gemini client which handles prompting and parsing.
    response = _gemini.extract_equations(problem)
    # The Gemini client returns a dict if possible; pass it through.
    return response


def _to_sympy_expressions(equations: List[str]) -> List[Any]:
    """
    Convert equation strings like 'x + y = 10' into sympy expressions equal to zero:
    e.g. 'x + y - 10'
    """
    exprs = []
    for eq in equations:
        if "=" in eq:
            left, right = eq.split("=", 1)
        else:
            # If user or extractor provided an expression without '=', treat as equals zero.
            left, right = eq, "0"
        try:
            left_s = sympify(left.strip())
            right_s = sympify(right.strip())
        except SympifyError as e:
            # Raise a helpful exception upstream to trigger fallback.
            raise ValueError(f"Failed to parse equation '{eq}' as SymPy expression: {e}") from e
        exprs.append(left_s - right_s)
    return exprs


def symbolic_solve(equations: List[str], variables: Optional[List[str]]) -> Any:
    """
    Use SymPy to solve the system.

    - Validate provided variables.
    - Convert equations to expressions equal to zero.
    - Call sympy.solve and serialize the result.

    On success, return a JSON-serializable structure (dict or list).
    On failure or SymPy exception, raise so the orchestrator can fallback.
    """
    if not equations:
        raise ValueError("No equations provided for symbolic solving.")

    # Convert to sympy expressions (expr = 0)
    exprs = _to_sympy_expressions(equations)

    # Determine symbols: use provided variables if given, otherwise infer.
    if variables:
        try:
            syms = symbols(",".join(variables))
            # symbols(...) returns a Symbol when one variable, or a tuple when many.
        except Exception as e:
            raise ValueError(f"Failed to construct symbols from variables {variables}: {e}") from e
    else:
        # Infer symbols by union of free symbols in expressions
        syms_set = set()
        for e in exprs:
            syms_set.update(e.free_symbols)
        if not syms_set:
            # No symbols detected -> nothing to solve
            raise ValueError("No variables found in equations.")
        syms = tuple(sorted(syms_set, key=lambda s: s.name))

    # Ensure we have a tuple/list of Symbol objects
    if isinstance(syms, Symbol):
        syms = [syms]
    else:
        syms = list(syms)

    # Use sympy.solve. This is the canonical symbolic solver.
    try:
        raw_solution = solve(exprs, syms, dict=True)
    except Exception as e:
        # Bubble up to orchestrator to trigger LLM fallback
        raise RuntimeError(f"SymPy raised an exception while solving: {e}") from e

    # sympy.solve returns a list of dicts (possibly empty) when dict=True
    if raw_solution is None:
        # No solution or solver did not return; treat as failure
        raise RuntimeError("SymPy returned None while solving.")

    # Convert sympy objects to plain Python types (strings are safe and unambiguous).
    serializable = []
    for sol in raw_solution:
        converted = {str(k): str(sol[k]) for k in sol}
        serializable.append(converted)

    # If the solution is empty list but system may be consistent with parameters, still return it.
    return serializable


def generate_explanation_with_gemini(original_problem: str, extracted: Dict[str, Any], sympy_solution: Any) -> str:
    """
    Ask Gemini to produce a human-friendly explanation of SymPy's result.

    Critical: Gemini MUST NOT recompute or override SymPy solution. It should only explain/interpret.
    """
    return _gemini.explain_solution(
        original_problem=original_problem,
        extracted=extracted,
        sympy_solution=sympy_solution,
    )


def fallback_gemini_reasoning(original_problem: str) -> Dict[str, Any]:
    """
    Use Gemini to perform step-by-step reasoning and numeric solving when:
    - extraction fails, OR
    - SymPy throws an exception

    Gemini is allowed to compute in this branch.
    """
    return _gemini.fallback_solve_and_explain(original_problem)