"""
Sanitizer for generated code.

Uses Python's AST to:
- Reject disallowed imports
- Reject usage of dangerous builtins and functions (eval, exec, open, __import__, etc.)
- Reject attribute access that looks like dunder or module access to sensitive modules.
- Auto-fix common LLM code generation mistakes
- Optionally rewrite or permit whitelisted constructs.

Sanitizer returns cleaned_code (which may be unchanged) or raises a SanitizationError.
Also provides utilities to extract JSON objects from messy LLM outputs.
"""
import ast
import logging
import re
from typing import List

logger = logging.getLogger("mathminds.sanitizer")


class SanitizationError(Exception):
    pass


# Allowed imports (module names)
ALLOWED_IMPORTS = {"sympy", "math", "fractions", "decimal", "numbers", "itertools", "functools"}

# Disallowed names (builtins or common dangerous functions)
DISALLOWED_NAMES = {
    "open",
    "exec",
    "eval",
    "compile",
    "__import__",
    "input",
    "os",
    "sys",
    "subprocess",
    "socket",
    "shutil",
    "requests",
    "urllib",
    "http",
    "ftplib",
    "pickle",
    "marshal",
    "ctypes",
    "multiprocessing",
    "threading",
    "fork",
    "pty",
}


def _extract_code_blocks(text: str) -> List[str]:
    """
    Extract triple-backtick code blocks (prefer those labelled python).
    Returns list of code strings; if none found, returns the entire text as single element.
    """
    code_blocks = []
    # Match ``` or ```python blocks
    pattern = re.compile(r"```(?:python)?\n(.*?)```", re.DOTALL | re.IGNORECASE)
    for m in pattern.finditer(text):
        code_blocks.append(m.group(1).strip())
    if code_blocks:
        return code_blocks
    # fallback: no code fences, return text
    return [text.strip()]


def _auto_fix_code(code: str) -> str:
    # 1. Fix malformed assignment-imports like "sp = import sympy as sp"
    # This pattern catches variations with extra assignments and spaces
    pattern_malformed_import = re.compile(
        r'^\s*(?:sp|sympy)\s*=\s*(?:(?:sp|sympy)\s*=\s*)?import\s+sympy\s+as\s+sp',
        re.MULTILINE | re.IGNORECASE
    )
    if pattern_malformed_import.search(code):
        code = pattern_malformed_import.sub('import sympy as sp', code)

    # 2. Fix the "chained" assignment version specifically
    code = code.replace("sp = sympy = import sympy as sp", "import sympy as sp")
    
    # ... rest of your existing fixes ...
    return code.strip()
    
    # Fix 3: Missing import statement but uses sp.* functions
    if 'sp.' in code and not re.search(r'import\s+sympy', code):
        code = "import sympy as sp\n" + code
        fixes_applied.append("Added missing import statement")
    
    # Fix 4: Using sympy.* without import
    if 'sympy.' in code and not re.search(r'import\s+sympy', code):
        code = "import sympy\n" + code
        fixes_applied.append("Added missing sympy import")
    
    # Fix 5: Remove duplicate import statements
    import_lines = []
    other_lines = []
    seen_imports = set()
    
    for line in code.split('\n'):
        stripped = line.strip()
        # Check if it's an import line
        if stripped.startswith('import sympy') or stripped.startswith('from sympy'):
            if stripped not in seen_imports:
                import_lines.append(line)
                seen_imports.add(stripped)
            else:
                fixes_applied.append(f"Removed duplicate import: {stripped}")
        else:
            other_lines.append(line)
    
    if len(import_lines) > 1:
        code = '\n'.join(import_lines + other_lines)
    
    # Fix 6: Ensure result variable exists if code doesn't assign to it
    if 'result' not in code and ('sp.solve' in code or 'sympy.solve' in code):
        # Try to detect the last meaningful line and assign it to result
        lines = code.split('\n')
        # Find the last non-empty, non-comment line
        for i in range(len(lines) - 1, -1, -1):
            line = lines[i].strip()
            if line and not line.startswith('#'):
                # Check if it's an expression (not an assignment)
                if '=' not in line or line.startswith('result'):
                    break
                # It's an assignment, let's make it assign to result instead
                if '=' in line and not line.startswith('result'):
                    var_name = line.split('=')[0].strip()
                    lines.append(f'result = {var_name}')
                    fixes_applied.append(f"Added result = {var_name}")
                    code = '\n'.join(lines)
                    break
    
    if fixes_applied:
        logger.info(f"Auto-fixes applied: {', '.join(fixes_applied)}")
        logger.debug(f"Original code:\n{original_code}")
        logger.debug(f"Fixed code:\n{code}")
    
    return code.strip()


def sanitize(raw_text: str) -> str:
    """
    Main sanitizer entrypoint. Accepts raw LLM text, extracts the best code block,
    applies auto-fixes, parses AST, enforces policies, and returns the sanitized code.

    Raises SanitizationError if code is disallowed or unfixable.
    """
    code_candidates = _extract_code_blocks(raw_text)

    last_err = None
    for code in code_candidates:
        try:
            # First, try to auto-fix common issues
            fixed_code = _auto_fix_code(code)
            
            # Then validate the AST
            _validate_ast(fixed_code)
            
            # Optionally normalize code formatting (simple stripping)
            cleaned = fixed_code.strip()
            return cleaned
        except SanitizationError as e:
            last_err = e
            logger.debug("Code candidate rejected: %s", e)
            continue
        except Exception as e:
            last_err = SanitizationError(f"Unexpected error: {e}")
            logger.debug("Unexpected error in sanitization: %s", e)
            continue

    # If none accepted, raise the last error
    raise SanitizationError(f"No acceptable code blocks found. Last error: {last_err}")


def _validate_ast(code: str):
    """
    Parse code into AST and enforce simple static rules.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        raise SanitizationError(f"Code could not be parsed: {e}")
    except Exception as e:
        raise SanitizationError(f"Code could not be parsed: {e}")

    # Walk AST for checks
    for node in ast.walk(tree):
        # Disallow import of unsafe modules
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name.split(".")[0]
                if name not in ALLOWED_IMPORTS:
                    raise SanitizationError(f"Import of '{name}' is not allowed.")
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            root = module.split(".")[0]
            if root not in ALLOWED_IMPORTS:
                raise SanitizationError(f"Import from '{module}' is not allowed.")

        # Disallow exec/eval/compile calls
        if isinstance(node, ast.Call):
            # function can be Name or Attribute
            func = node.func
            if isinstance(func, ast.Name):
                if func.id in DISALLOWED_NAMES:
                    raise SanitizationError(f"Use of '{func.id}' is not allowed.")
            elif isinstance(func, ast.Attribute):
                attr_chain = _attribute_to_str(func)
                for bad in DISALLOWED_NAMES:
                    if bad in attr_chain:
                        raise SanitizationError(f"Use of '{attr_chain}' is not allowed.")

        # Disallow usage of names in global context
        if isinstance(node, ast.Name):
            if node.id in DISALLOWED_NAMES:
                raise SanitizationError(f"Usage of name '{node.id}' is not allowed.")

        # Disallow dunder access (e.g., __dict__, __class__, etc.)
        if isinstance(node, ast.Attribute):
            attr = node.attr
            if attr.startswith("__") and attr.endswith("__"):
                raise SanitizationError(f"Access to dunder attribute '{attr}' is not allowed.")
            # Also check full attribute chain for banned module names
            chain = _attribute_to_str(node)
            for bad in DISALLOWED_NAMES:
                if chain.startswith(bad + ".") or ("." + bad + ".") in chain or chain.endswith("." + bad):
                    raise SanitizationError(f"Attribute access to '{chain}' is not allowed.")

    # Additional heuristics: disallow overly long code (avoid hidden scraping loops)
    if len(code) > 40_000:
        raise SanitizationError("Code is too long.")

    # If we reach here, code is considered syntactically allowed
    return True


def _attribute_to_str(node: ast.Attribute) -> str:
    """
    Convert an Attribute node to a dotted string (best-effort).
    """
    parts = []
    current = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
    parts.reverse()
    return ".".join(parts)


class LLMSanitizer:
    """
    Utilities for cleaning LLM outputs that are expected to contain JSON or code.

    This class groups helpers that extract JSON blocks from messy LLM outputs,
    strip markdown fences, and provide safe defaults.
    """

    @staticmethod
    def sanitize_llm_json(raw_text: str) -> str:
        """
        Extracts the first valid JSON object from messy LLM output.
        Handles markdown blocks and conversational text.

        Returns the JSON string fragment if found, otherwise returns an empty JSON object "{}".
        """
        if not raw_text or not isinstance(raw_text, str):
            return "{}"

        # Try markdown fenced JSON first (```json ... ``` or ``` ... ```)
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