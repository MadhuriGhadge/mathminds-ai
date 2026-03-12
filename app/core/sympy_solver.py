import logging
import sympy
from sympy.parsing.sympy_parser import parse_expr, standard_transformations, implicit_multiplication_application, convert_xor
from typing import Optional, Any
from app.core.math_normalizer import MathIntent

logger = logging.getLogger(__name__)

class SymPySolver:
    """
    Attempts to solve mathematical expressions using SymPy.
    Used as a pre-flight check to save LLM quota for pure math.
    """

    def solve(self, intent: MathIntent) -> Optional[str]:
        """
        Processes a MathIntent and returns a formatted solution string or None.
        """
        try:
            expr_str = intent.expression
            action = intent.intent
            var_symbol = sympy.Symbol(intent.variable or 'x')

            if action == "derivative":
                return self._solve_derivative(expr_str, var_symbol)
            elif action == "integral":
                return self._solve_integral(expr_str, var_symbol)
            elif action == "equation":
                return self._solve_equation(expr_str, var_symbol)
            elif action == "arithmetic":
                return self._solve_arithmetic(expr_str)
            
            return None
        except Exception as e:
            logger.info(f"SymPy could not solve '{intent.expression}': {e}")
            return None

    def _parse(self, expr_str: str) -> Any:
        transformations = standard_transformations + (implicit_multiplication_application, convert_xor)
        return parse_expr(expr_str, transformations=transformations)

    def _solve_derivative(self, expr_str: str, var: sympy.Symbol) -> Optional[str]:
        expr = self._parse(expr_str)
        result = sympy.diff(expr, var)
        return f"The derivative of ${sympy.latex(expr)}$ with respect to ${var}$ is:\n\n$${sympy.latex(result)}$$"

    def _solve_integral(self, expr_str: str, var: sympy.Symbol) -> Optional[str]:
        expr = self._parse(expr_str)
        result = sympy.integrate(expr, var)
        # Check if integral was actually solved (not just returned as an Integral object)
        if isinstance(result, sympy.Integral):
            return None
        return f"The indefinite integral of ${sympy.latex(expr)}$ with respect to ${var}$ is:\n\n$${sympy.latex(result)} + C$$"

    def _solve_equation(self, expr_str: str, var: sympy.Symbol) -> Optional[str]:
        # Handle equations like "x^2 - 4 = 0" or "x^2 = 4"
        if "=" in expr_str:
            lhs_str, rhs_str = expr_str.split("=")
            lhs = self._parse(lhs_str.strip())
            rhs = self._parse(rhs_str.strip())
            eq = sympy.Eq(lhs, rhs)
        else:
            # Assume expression = 0 if no '='
            eq = self._parse(expr_str)

        solutions = sympy.solve(eq, var)
        if not solutions:
            return "No solutions found."
        
        sol_str = ", ".join([f"${sympy.latex(s)}$" for s in solutions])
        return f"The solutions for ${sympy.latex(eq if '=' in expr_str else sympy.Eq(self._parse(expr_str), 0))}$ are:\n\n{sol_str}"

    def _solve_arithmetic(self, expr_str: str) -> Optional[str]:
        # SAFETY CHECK: reject expressions containing non-math words
        # If the expression has alphabetic characters that aren't recognised
        # math symbols (e, i, pi, x, y, z, etc.), SymPy silently treats each
        # letter as a variable and multiplies them together — producing garbled
        # output like "45aeflouv" on the UI.
        # Example: "the value of 5*9" → SymPy sees t*h*e*v*a*l*u*e*o*f*5*9
        #
        # Rule: if the expression contains any English word characters beyond
        # known math constants, return None and let Gemini handle it.
        import re
        # Strip pure math tokens to see what's left
        stripped = re.sub(r'[0-9+\-*/^().\s]', '', expr_str)
        # Known single-letter math constants that SymPy handles correctly
        safe_single_letters = set('eijxyz')
        # Known multi-letter constants/functions
        safe_words = {'pi', 'inf', 'oo', 'sin', 'cos', 'tan', 'log', 'exp',
                      'sqrt', 'abs', 'floor', 'ceil'}
        
        # Check for multi-char letter sequences (words) that aren't math
        words_in_expr = re.findall(r'[a-zA-Z]+', expr_str)
        for word in words_in_expr:
            if word.lower() not in safe_words and len(word) > 1:
                # Multi-letter word that isn't a math function — natural language crept in
                logger.debug(f"SymPy arithmetic rejected: found word '{word}' in '{expr_str}'")
                return None
        
        try:
            expr = self._parse(expr_str)
            result = expr.evalf() if expr.is_number else sympy.simplify(expr)
            
            # If result is same as input and not a simple number, let Gemini handle it
            if str(result) == expr_str and not result.is_number:
                return None
            
            # Format result cleanly — integer if possible, float otherwise
            try:
                numeric = float(result)
                if numeric == int(numeric):
                    display = str(int(numeric))
                else:
                    display = f"{numeric:.4f}".rstrip('0').rstrip('.')
                return f"Result: **{display}**\n\n$${ sympy.latex(self._parse(expr_str))} = {sympy.latex(result)}$$"
            except Exception:
                return f"Result of evaluation:\n\n$${sympy.latex(result)}$$"
        except Exception as e:
            logger.debug(f"SymPy arithmetic eval failed for '{expr_str}': {e}")
            return None