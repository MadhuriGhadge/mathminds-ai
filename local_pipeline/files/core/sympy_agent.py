"""
Helper utilities around SymPy-focused agent logic.

This file exposes helpers that build prompts and post-process results from
SymPy-related code execution.
"""
import logging
import re
from typing import Optional

from core.prompt_templates import GEN_SYMPY_CODE, EXPLAIN_RESULT
from core.llm_client import LLMClient

logger = logging.getLogger("mathminds.sympy_agent")


def build_sympy_code_prompt(problem: str) -> str:
    """
    Build the prompt to instruct the LLM to generate SymPy Python code.
    """
    return GEN_SYMPY_CODE.format(problem=problem)


def build_explain_prompt(problem: str, code: str, execution_result) -> str:
    """
    Build the prompt to instruct the LLM to explain the execution result.
    """
    return EXPLAIN_RESULT.format(problem=problem, code=code, execution_result=execution_result)


def extract_code_from_response(text: str) -> str:
    """
    Extract Python code from the LLM response with multiple fallback strategies.
    
    Strategies:
    1. Look for ```python ... ``` code blocks
    2. Look for ``` ... ``` code blocks
    3. Clean up malformed import statements
    4. Use the raw text if it looks like code
    """
    if not text or not isinstance(text, str):
        return ""
    
    # Strategy 1: Try to find ```python code block
    m = re.search(r"```python\s*\n(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if m:
        code = m.group(1).strip()
        return _fix_common_issues(code)
    
    # Strategy 2: Try to find ``` code block (without language)
    m = re.search(r"```\s*\n(.*?)```", text, re.DOTALL)
    if m:
        code = m.group(1).strip()
        return _fix_common_issues(code)
    
    # Strategy 3: Try to find code after "```python" without closing
    m = re.search(r"```python\s*\n(.*)", text, re.DOTALL | re.IGNORECASE)
    if m:
        code = m.group(1).strip()
        # Remove trailing ``` if present
        code = re.sub(r'```\s*$', '', code).strip()
        return _fix_common_issues(code)
    
    # Strategy 4: If text starts with "import" or contains "sp.solve", treat as code
    stripped = text.strip()
    if (stripped.startswith('import ') or 
        stripped.startswith('from ') or
        'sp.solve' in stripped or
        'sympy.solve' in stripped):
        return _fix_common_issues(stripped)
    
    # Strategy 5: Last resort - return cleaned text
    return _fix_common_issues(text.strip())


def _fix_common_issues(code: str) -> str:
    """
    Fix common code generation issues.
    """
    if not code:
        return code
    
    # Fix: "sp = sympy = import sympy as sp" → "import sympy as sp"
    code = re.sub(
        r'^\s*(?:sp|sympy)\s*=\s*(?:sp|sympy)\s*=\s*import\s+sympy\s+as\s+sp',
        'import sympy as sp',
        code,
        flags=re.MULTILINE
    )
    
    # Fix: "sp = import sympy as sp" → "import sympy as sp"
    code = re.sub(
        r'^\s*(?:sp|sympy)\s*=\s*import\s+sympy\s+as\s+sp',
        'import sympy as sp',
        code,
        flags=re.MULTILINE
    )
    
    # Fix: Multiple import statements for sympy (keep first, remove duplicates)
    import_lines = []
    other_lines = []
    seen_import = False
    
    for line in code.split('\n'):
        stripped = line.strip()
        if stripped.startswith('import sympy') or stripped.startswith('from sympy'):
            if not seen_import:
                import_lines.append(line)
                seen_import = True
        else:
            other_lines.append(line)
    
    if import_lines:
        code = '\n'.join(import_lines + other_lines)
    
    # Remove any leading/trailing whitespace
    code = code.strip()
    
    return code