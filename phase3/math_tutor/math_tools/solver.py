import sympy as sp
import re

def normalize_expression(expr: str) -> str:
    expr = expr.replace("^", "**")
    # convert implicit multiplication: 5x -> 5*x
    expr = re.sub(r'(\d)([a-zA-Z])', r'\1*\2', expr)
    return expr


def solve_mathematical_problem(problem: str) -> dict:
    result = {
        "original": problem,
        "normalized": None,
        "steps": [],
        "solution": None,
        "error": None
    }

    try:
        normalized = normalize_expression(problem)
        result["normalized"] = normalized
        result["steps"].append(f"Normalized expression: {normalized}")

        expr = sp.sympify(normalized)
        x = sp.symbols('x')

        solution = sp.solve(expr, x)
        result["steps"].append("Solved equation for x")
        result["solution"] = solution

    except Exception as e:
        result["error"] = str(e)

    return result
