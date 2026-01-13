"""
Validation and helper utilities.

Responsibilities:
- Validate Gemini extraction conforms to the required structure.
- Additional small helpers used across the project.

Keep these functions small and pure for testability.
"""
from typing import Any, Dict


def ensure_valid_extraction(extraction: Any) -> bool:
    """
    Verify the extraction dict matches the required contract:
    {
      "equations": [...],
      "variables": [...]
    }
    Return True if valid and contains at least one equation.
    """
    if not isinstance(extraction, dict):
        return False
    eqs = extraction.get("equations")
    vars_ = extraction.get("variables")
    if not isinstance(eqs, list) or not isinstance(vars_, list):
        return False
    # Require at least one equation to attempt symbolic solving.
    if len(eqs) == 0:
        return False
    # Ensure each equation is a non-empty string.
    for e in eqs:
        if not isinstance(e, str) or not e.strip():
            return False
    for v in vars_:
        if not isinstance(v, str) or not v.strip():
            return False
    return True