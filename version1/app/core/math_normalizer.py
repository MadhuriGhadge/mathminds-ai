import re
from typing import Optional, Dict, Any
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

@dataclass
class MathIntent:
    intent: str
    expression: str
    variable: Optional[str] = 'x'
    original_query: str = ""

class MathQueryNormalizer:
    """
    Normalizes natural language math queries into structured intents
    resolvable by symbolic solvers.
    """
    
    def __init__(self):
        self.intent_patterns = {
            "derivative": [
                r"derivative of\s+(.+)",
                r"derive\s+(.+)",
                r"differentiate\s+(.+)",
                r"d/dx\s*\[?(.+)\]?"
            ],
            "integral": [
                r"integral of\s+(.+)",
                r"integrate\s+(.+)",
                r"antiderivative of\s+(.+)"
            ],
            "limit": [
                r"limit of\s+(.+)\s+as\s+(\w+)\s+approaches\s+(.+)",
                r"lim\s+(.+)"
            ],
            "equation": [
                r"solve\s+(.+)",
                r"find x for\s+(.+)", # basic
                r"(.+)=(.+)" # implicit equation if contains =
            ],
            "arithmetic": [
                r"calculate\s+(.+)",
                r"what is\s+(.+)",
                r"evaluate\s+(.+)"
            ]
        }
        
        # Stop words to clean from expression
        self.stop_words = ["what is", "calculate", "the", "please", "solve", "evaluate"]

    def normalize(self, text: str) -> Optional[MathIntent]:
        """
        Parses text to identify math intent and extract the core expression.
        Returns None if no clear math intent is found.
        """
        if not text:
            return None
            
        clean_text = text.lower().strip().rstrip("?")
        
        # 1. Check specific intents
        
        # Derivative
        for pattern in self.intent_patterns["derivative"]:
            match = re.search(pattern, clean_text)
            if match:
                # Group 1 is usually the expression
                raw_expr = match.group(1)
                expr = self._clean_expression(raw_expr)
                return MathIntent(
                    intent="derivative",
                    expression=expr,
                    variable='x', 
                    original_query=text
                )

        # Integral
        for pattern in self.intent_patterns["integral"]:
            match = re.search(pattern, clean_text)
            if match:
                raw_expr = match.group(1)
                expr = self._clean_expression(raw_expr)
                return MathIntent(
                    intent="integral",
                    expression=expr,
                    variable='x',
                    original_query=text
                )
                
        # Equation Solving
        if "=" in clean_text:
             # Basic heuristic: if it has = it's likely an equation
             # Remove "solve", "find x" etc
             expr = clean_text
             for stop in ["solve", "find x", "calculate", "what is", "evaluate"]:
                 expr = expr.replace(stop, "")
             
             return MathIntent(
                 intent="equation",
                 expression=expr.strip(),
                 variable='x',
                 original_query=text
             )

        # Arithmetic / Simplification
        # If it looks like math chars only
        if self._is_arithmetic(clean_text):
             return MathIntent(
                 intent="arithmetic",
                 expression=clean_text,
                 original_query=text
             )

        return None

    def _clean_expression(self, text: str) -> str:
        """Removes common stop words and artifacts."""
        text = text.strip()
        
        # Remove "what is" if it somehow got in
        for stop in self.stop_words:
             # Replace start of string
             if text.startswith(stop):
                 text = text[len(stop):].strip()
        
        return text.strip()

    def _is_arithmetic(self, text: str) -> bool:
        """
        Checks if text is primarily arithmetic (numbers, operators).
        """
        # Allow basic math chars
        allowed_chars = set("0123456789+-*/^().= \t")
        
        # 1. Must contain at least one digit
        if not any(c.isdigit() for c in text):
            return False
            
        # 2. Must only contain allowed chars [and maybe 'x', 'y' for algebra?]
        # Let's be strict for "arithmetic" intent, looser for "algebra" if we had it.
        # But user query "2x + 5" is algebra/simplification.
        
        # Let's allow algebraic vars for simplification
        allowed_chars.update(set("xyzabc")) 
        
        # Check if characters are valid
        for char in text:
            if char not in allowed_chars:
                return False
                
        return True
