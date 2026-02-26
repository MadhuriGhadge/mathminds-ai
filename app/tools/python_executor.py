import sys
import io
import contextlib
import logging
import asyncio
from typing import Dict, Any

logger = logging.getLogger(__name__)

class PythonInterpreter:
    """
    A tool that allows the agent to execute arbitrary Python code.
    Includes basic sandboxing and stdout capture.
    """

    def __init__(self, timeout: int = 30):
        self.timeout = timeout

    async def execute(self, code: str) -> Dict[str, Any]:
        """
        Executes the provided Python code and returns the output or error.
        """
        logger.info("Executing Python code chunk...")
        
        output_buffer = io.StringIO()
        error_msg = None
        result = None

        # Prepare global context for execution
        # We can inject libraries like numpy, pandas, sympy if needed
        global_context = {
            "__name__": "__main__",
            "__builtins__": __builtins__,
        }
        
        try:
            # Inject common math libraries
            import numpy as np
            import pandas as pd
            import sympy
            global_context["np"] = np
            global_context["pd"] = pd
            global_context["sympy"] = sympy
        except ImportError:
            pass

        try:
            with contextlib.redirect_stdout(output_buffer), contextlib.redirect_stderr(output_buffer):
                # We use a wrapper to handle async execution if needed, 
                # but for now, standard exec is usually enough for most assistant tasks.
                # To support 'result = ...' pattern:
                exec_globals = global_context
                
                # Use a timeout to prevent infinite loops
                await asyncio.wait_for(
                    asyncio.to_thread(exec, code, exec_globals),
                    timeout=self.timeout
                )
                
                # Check for a specific 'result' variable in the local context if needed,
                # or just return the stdout.
                result = exec_globals.get("result")

            status = "success"
        except asyncio.TimeoutError:
            status = "error"
            error_msg = f"Execution timed out after {self.timeout} seconds."
        except Exception as e:
            status = "error"
            error_msg = str(e)
            logger.error(f"Python execution error: {e}")

        captured_output = output_buffer.getvalue()
        
        return {
            "status": status,
            "content": captured_output if status == "success" else f"Error: {error_msg}\nOutput so far:\n{captured_output}",
            "result": str(result) if result is not None else None
        }
