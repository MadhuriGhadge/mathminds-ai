import logging
import os
from typing import Dict, Any, Optional
import sympy
from sympy.parsing.sympy_parser import parse_expr

# Try importing wolframalpha, handling if not installed or configured
try:
    import wolframalpha
except ImportError:
    wolframalpha = None

logger = logging.getLogger(__name__)

class SymbolicSolver:
    """
    Tool for solving math problems symbolically.
    Prioritizes WolframAlpha (if AppID present), falls back to SymPy.
    """

    def __init__(self, wolfram_app_id: Optional[str] = None):
        self.wolfram_app_id = wolfram_app_id or os.getenv("WOLFRAM_APP_ID")
        self.wolfram_client = None
        
        if self.wolfram_app_id and wolframalpha:
            try:
                self.wolfram_client = wolframalpha.Client(self.wolfram_app_id)
            except Exception as e:
                logger.warning(f"Failed to initialize WolframAlpha client: {e}")

    def solve(self, query: str) -> Dict[str, Any]:
        """
        Attempts to solve the query symbolically.
        """
        logger.info(f"SymbolicSolver triggered for query: {query}")

        # 1. Try WolframAlpha
        if self.wolfram_client:
            try:
                res = self.wolfram_client.query(query)
                # Wolfram returns pods. We want the 'Result' pod usually.
                # Simplification: gather text from all pods
                answer_text = ""
                for pod in res.pods:
                    for sub in pod.subpods:
                        if sub.plaintext:
                            answer_text += f"{pod.title}: {sub.plaintext}\n"
                
                if answer_text:
                    return {
                        "source": "wolfram_alpha",
                        "content": answer_text,
                        "status": "success"
                    }
                    
            except Exception as e:
                logger.warning(f"WolframAlpha query failed: {e}")
                # Fallthrough to SymPy

        # 2. Try SymPy (Local Fallback)
        try:
            # Very basic SymPy handling for "integrate x^2" type queries
            # This is brittle but serves as a proof-of-concept fallback
            
            # Simple keyword matching to guess operation
            normalized = query.lower()
            result_latex = ""
            
            if "integrate" in normalized:
                # Extract expression (naive split)
                # e.g. "integrate x**2" -> "x**2"
                expr_str = normalized.replace("integrate", "").strip()
                x = sympy.symbols('x')
                expr = parse_expr(expr_str)
                res = sympy.integrate(expr, x)
                result_latex = sympy.latex(res)
                
            elif "derivative" in normalized or "derive" in normalized:
                expr_str = normalized.replace("derivative of", "").replace("derive", "").strip()
                x = sympy.symbols('x')
                expr = parse_expr(expr_str)
                res = sympy.diff(expr, x)
                result_latex = sympy.latex(res)

            else:
                 # Attempt to just simplify
                 x = sympy.symbols('x') # Assume x variable
                 expr = parse_expr(normalized)
                 res = sympy.simplify(expr)
                 result_latex = sympy.latex(res)

            return {
                "source": "sympy_local",
                "content": f"Result: ${result_latex}$",
                "status": "success"
            }

        except Exception as e:
            logger.error(f"Symbolic solving failed: {e}")
            return {
                "source": "symbolic_solver",
                "error": str(e),
                "status": "error"
            }
