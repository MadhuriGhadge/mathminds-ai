import logging
import os
from typing import Dict, Any, Optional, Union
import sympy
from sympy.parsing.sympy_parser import parse_expr
from app.core.math_normalizer import MathIntent

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
        
        logger.info(f"Initializing SymbolicSolver. WolframAppID present: {bool(self.wolfram_app_id)}")
        
        if self.wolfram_app_id and wolframalpha:
            try:
                logger.info("Attempting to create WolframAlpha client...")
                self.wolfram_client = wolframalpha.Client(self.wolfram_app_id)
                logger.info("WolframAlpha client created.")
            except Exception as e:
                logger.warning(f"Failed to initialize WolframAlpha client: {e}")

    def solve(self, query: Union[str, MathIntent]) -> Dict[str, Any]:
        """
        Attempts to solve the query symbolically.
        Accepts either a raw string (tried via Wolfram) or a structured MathIntent (for SymPy).
        """
        # Unwrap intent if passed
        intent = None
        raw_query = query
        if isinstance(query, MathIntent):
            intent = query
            raw_query = intent.original_query or intent.expression
        
        logger.info(f"SymbolicSolver triggered for query: {raw_query}")
        
        # 1. Try WolframAlpha (best for natural language or complex stuff)
        if self.wolfram_client:
            try:
                 # Wolfram prefers natural language usually
                res = self.wolfram_client.query(raw_query)
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
                
        # 2. Try SymPy (Local Fallback)
        # We need a structured intent for SymPy to work reliably. 
        # If we just got a string and Wolfram failed, we can't easily use SymPy 
        # unless it was already normalized.
        
        if not intent:
            return {
                "source": "symbolic_solver",
                "error": "WolframAlpha failed and no structured MathIntent provided for SymPy.",
                "status": "error"
            }
            
        try:
            # Pre-processing for SymPy syntax
            # handle power operator ^ -> **
            expr_str = intent.expression.replace("^", "**")
            
            # handle implicit multiplication (simple regex)
            import re
            expr_str = re.sub(r'(\d)([a-z])', r'\1*\2', expr_str)
            expr_str = re.sub(r'\)\(', ')*(', expr_str)
            
            target_var = sympy.symbols(intent.variable or 'x')
            result_latex = ""
            
            if intent.intent == "derivative":
                expr = parse_expr(expr_str)
                res = sympy.diff(expr, target_var)
                result_latex = sympy.latex(res)
                
            elif intent.intent == "integral":
                expr = parse_expr(expr_str)
                res = sympy.integrate(expr, target_var)
                result_latex = sympy.latex(res)
                
            elif intent.intent == "equation":
                # Expecting "lhs = rhs" or just expression assumed = 0
                parts = expr_str.split("=")
                if len(parts) == 2:
                    lhs = parse_expr(parts[0])
                    rhs = parse_expr(parts[1])
                    solution = sympy.solve(lhs - rhs, target_var)
                else:
                    # Assume expr = 0
                    expr = parse_expr(expr_str)
                    solution = sympy.solve(expr, target_var)
                    
                result_latex = sympy.latex(solution)
                
            elif intent.intent == "limit":
                # TODO: Parsing limits needs 'approaches' value, logic not fully here yet
                # Fallback implementation
                return {"source": "symbolic_solver", "status": "error", "error": "Limit parsing not fully implemented"}

            elif intent.intent == "arithmetic" or intent.intent == "simplification":
                 expr = parse_expr(expr_str)
                 res = sympy.simplify(expr)
                 result_latex = sympy.latex(res)
            
            else:
                 return {"source": "symbolic_solver", "status": "error", "error": f"Unknown intent: {intent.intent}"}

            return {
                "source": "sympy_local",
                "content": result_latex,
                "status": "success"
            }

        except Exception as e:
            logger.warning(f"SymPy execution failed: {e}")
            return {
                "source": "symbolic_solver",
                "error": str(e),
                "status": "error"
            }
