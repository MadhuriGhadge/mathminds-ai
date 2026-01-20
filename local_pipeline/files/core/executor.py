"""
Safe executor for running sanitized SymPy Python code.

Execution strategy:
- Create a separate process for execution to enforce timeouts and resource limits.
- Provide a tightly controlled globals mapping:
    - Only a minimal set of builtins are exposed.
    - Pre-imported modules: sympy as sp, math
    - Custom __import__ that only allows whitelisted modules
- Capture stdout/stderr and the final 'result' variable (if present).
- Return structured execution output including success flag, result, stdout, stderr, and exceptions.
"""
import io
import json
import logging
import multiprocessing as mp
import sys
import textwrap
import traceback
from dataclasses import dataclass
from typing import Any, Dict, Optional

# resource module is Unix-only; wrap in try
try:
    import resource
except Exception:
    resource = None

import math
import sympy as sp

logger = logging.getLogger("mathminds.executor")

# Whitelist of allowed modules for import
ALLOWED_MODULES = {
    "sympy",
    "math",
    "fractions",
    "decimal",
    "numbers",
    "itertools",
    "functools",
    "collections",
}


@dataclass
class ExecutionOutput:
    success: bool
    result: Optional[Any] = None
    stdout: str = ""
    stderr: str = ""
    error: Optional[str] = None
    meta: Dict[str, Any] = None

    def to_dict(self):
        return {
            "success": self.success,
            "result": self.result,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "error": self.error,
            "meta": self.meta or {},
        }


def _safe_builtins():
    """
    Return a minimal set of safe builtins.
    """
    allowed = [
        "abs",
        "all",
        "any",
        "bin",
        "bool",
        "chr",
        "complex",
        "dict",
        "float",
        "int",
        "len",
        "list",
        "map",
        "max",
        "min",
        "pow",
        "range",
        "reversed",
        "round",
        "set",
        "slice",
        "sorted",
        "str",
        "sum",
        "tuple",
        "enumerate",
        "zip",
        "filter",
        "isinstance",
        "issubclass",
        "type",
        "callable",
        "hasattr",
        "getattr",
        "setattr",
        "delattr",
    ]
    safe = {k: __builtins__[k] for k in allowed if k in __builtins__}
    # Provide a dummy print that writes to stdout still captured by io
    safe["print"] = print
    return safe


def _create_safe_import():
    """
    Create a custom __import__ function that only allows whitelisted modules.
    
    This allows generated code to use 'import sympy' while blocking dangerous imports.
    """
    # Store reference to the real __import__
    real_import = __builtins__.__import__
    
    def safe_import(name, globals=None, locals=None, fromlist=(), level=0):
        """
        Custom import function that only allows whitelisted modules.
        
        Args:
            name: Module name to import
            globals: Global namespace (unused in our implementation)
            locals: Local namespace (unused in our implementation)
            fromlist: List of names to import from module
            level: Relative import level (0 = absolute)
        
        Raises:
            ImportError: If module is not in whitelist
        """
        # Get the root module name (before any dots)
        root_module = name.split('.')[0]
        
        # Check if the root module is allowed
        if root_module not in ALLOWED_MODULES:
            raise ImportError(
                f"Import of '{name}' is not allowed. "
                f"Allowed modules: {', '.join(sorted(ALLOWED_MODULES))}"
            )
        
        # For relative imports, reject them (level > 0)
        if level > 0:
            raise ImportError("Relative imports are not allowed")
        
        # If fromlist is specified, validate those too
        # This handles: from sympy import Symbol
        if fromlist:
            for item in fromlist:
                # Allow imports from submodules of allowed modules
                # e.g., "from sympy.abc import x" is OK if sympy is allowed
                if item.startswith('_'):
                    raise ImportError(
                        f"Import of private attribute '{item}' from '{name}' is not allowed"
                    )
        
        # All checks passed, delegate to real import
        try:
            return real_import(name, globals, locals, fromlist, level)
        except Exception as e:
            # Re-raise import errors with context
            raise ImportError(f"Failed to import '{name}': {e}")
    
    return safe_import


def _runner(code: str, queue: mp.Queue):
    """
    Target function to run inside a child process. Executes code in a restricted
    environment and places ExecutionOutput (as dict) on the queue.
    """
    # Enforce resource limits if available (Unix)
    try:
        if resource:
            # 200MB memory cap (address space)
            mem_bytes = 200 * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))
            # 5 seconds CPU time
            resource.setrlimit(resource.RLIMIT_CPU, (5, 5))
    except Exception:
        # Not fatal; continue without resource limits
        pass

    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()

    # Prepare restricted globals and locals
    safe_globals = {
        "__builtins__": _safe_builtins(),
        "__import__": _create_safe_import(),  # Custom import function
        "sp": sp,
        "sympy": sp,
        "math": math,
    }
    local_vars = {}

    try:
        # Redirect stdout/stderr
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = stdout_buf
        sys.stderr = stderr_buf

        # Execute the code
        # We wrap code in a textwrap.dedent to handle indentation
        exec(textwrap.dedent(code), safe_globals, local_vars)

        # Gather the 'result' if present
        result = local_vars.get("result", None)
        out = ExecutionOutput(success=True, result=_serialize_result(result))
    except ImportError as e:
        # Special handling for import errors to make them clear
        tb = traceback.format_exc()
        out = ExecutionOutput(
            success=False, 
            result=None, 
            error=f"Import Error: {str(e)}\n\n{tb}"
        )
    except Exception as e:
        tb = traceback.format_exc()
        out = ExecutionOutput(success=False, result=None, error=tb)
    finally:
        # Restore stdout/stderr
        sys.stdout = old_stdout
        sys.stderr = old_stderr

    # Attach captured outputs
    out.stdout = stdout_buf.getvalue()
    out.stderr = stderr_buf.getvalue()
    
    # Put dict on queue (must be serializable)
    try:
        queue.put(out.to_dict())
    except Exception as e:
        # As a last resort, put minimal failure info
        queue.put(
            {
                "success": False,
                "result": None,
                "stdout": out.stdout,
                "stderr": out.stderr,
                "error": f"Failed to send result: {e}",
                "meta": {},
            }
        )


def _serialize_result(value):
    """
    Convert sympy or python objects into JSON-serializable forms if possible.
    """
    try:
        if value is None:
            return None
        
        # Handle lists and tuples
        if isinstance(value, (list, tuple)):
            return [_serialize_result(v) for v in value]
        
        # Handle dictionaries
        if isinstance(value, dict):
            return {k: _serialize_result(v) for k, v in value.items()}
        
        # Sympy expressions: convert to string or to sympy.srepr for structured representation
        if hasattr(value, "__module__") and value.__module__.startswith("sympy"):
            try:
                result_dict = {"sympy": str(value)}
                
                # Try to get numeric evaluation
                if hasattr(value, "evalf"):
                    try:
                        numeric = str(value.evalf())
                        result_dict["numeric"] = numeric
                    except Exception:
                        pass
                
                # For expressions, try to get LaTeX representation
                if hasattr(value, "__class__") and hasattr(sp, "latex"):
                    try:
                        latex = sp.latex(value)
                        result_dict["latex"] = latex
                    except Exception:
                        pass
                
                return result_dict
            except Exception:
                return {"sympy": str(value)}
        
        # Basic Python types are fine
        if isinstance(value, (str, int, float, bool)):
            return value
        
        # Fallback to string
        return str(value)
    except Exception:
        return str(value)


def execute(code: str, timeout: int = 8) -> ExecutionOutput:
    """
    Execute sanitized code in a separate process with timeout enforcement.
    Returns an ExecutionOutput dataclass.
    """
    queue: mp.Queue = mp.Queue()
    proc = mp.Process(target=_runner, args=(code, queue))
    proc.start()
    proc.join(timeout)
    
    if proc.is_alive():
        proc.terminate()
        proc.join()
        return ExecutionOutput(
            success=False,
            result=None,
            stdout="",
            stderr="",
            error=f"Execution timed out after {timeout} seconds.",
            meta={"timeout": timeout},
        )
    
    # Try to get output from queue
    try:
        out = queue.get_nowait()
        # out is a dict, convert to dataclass for convenience
        return ExecutionOutput(
            success=out.get("success", False),
            result=out.get("result"),
            stdout=out.get("stdout", ""),
            stderr=out.get("stderr", ""),
            error=out.get("error"),
            meta=out.get("meta", {}),
        )
    except Exception as e:
        return ExecutionOutput(
            success=False,
            result=None,
            stdout="",
            stderr="",
            error=f"No output received from execution process: {e}",
            meta={},
        )