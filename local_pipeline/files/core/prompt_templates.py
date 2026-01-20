"""
Prompt templates used across the system.

Templates are intentionally modular and extensible so future agents (OCR,
Redis lookups, other LLMs) can reuse or extend them.
"""
from typing import Dict

# Template for generating SymPy Python code to solve math problems.
# The model is instructed to return only Python code, and to assign the final
# answer to a variable named `result`. Use triple backticks around code blocks
# is encouraged by some models; agents will extract code blocks if present.
GEN_SYMPY_CODE = """You are an expert Python programmer. Generate valid Python code to solve this math problem using SymPy.

IMPORTANT RULES:
1. Start with: import sympy as sp
2. Use sp.Symbol() to define variables
3. Use sp.solve() to solve equations
4. Store the final answer in a variable named 'result'
5. Write ONLY valid Python code - no explanations, no comments
6. The code must be syntactically correct and executable

Problem: {problem}

Generate the Python code below:
```python"""

# Template for asking the LLM to explain the executed result and steps.
EXPLAIN_RESULT = """You are an assistant that explains math solutions produced by code.

Context:
- The user's original problem: {problem}
- The code that was executed:
```python
{code}
```
- The execution result: {execution_result}

Provide a clear, concise explanation of:
1. What the problem asked for
2. How the code solved it
3. What the final answer means

Explanation:"""

# Hints used by the Router to categorize queries
ROUTER_HINTS = {
    "math": [
        "solve", "calculate", "derivative", "integral", "equation", 
        "simplify", "factor", "limit", "matrix", "algebra"
    ],
    "logic": [
        "prove", "implies", "if and only if", "boolean", "truth table", 
        "logical", "proposition", "negation", "and", "or", "xor"
    ]
}