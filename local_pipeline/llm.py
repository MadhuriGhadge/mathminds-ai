import ollama
import sympy as sp
import sys
from io import StringIO
import re

MODEL = "qwen2.5:3b-instruct-q4_K_M"

SYSTEM_PROMPT = """
You are a Python math solver.

Rules:
- Use sympy as: import sympy as sp
- Always define symbols explicitly
- If equation is transcendental, use sp.nsolve
- Always print a numeric decimal answer (use evalf())
- Print only the final answer
- Output ONLY python code
"""

def sanitize(code: str) -> str:
    code = re.sub(r"```.*?```", "", code, flags=re.S)
    code = code.replace("```", "")
    return code.strip()

def solve(problem: str):
    response = ollama.chat(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": problem}
        ]
    )

    raw_code = response["message"]["content"]
    code = sanitize(raw_code)

    old_stdout = sys.stdout
    sys.stdout = buffer = StringIO()

    try:
        exec(code, {"sp": sp})
        output = buffer.getvalue()
    except Exception as e:
        return f"Execution error:\n{e}\n\nGenerated code:\n{code}"
    finally:
        sys.stdout = old_stdout

    return output.strip()

if __name__ == "__main__":
    while True:
        q = input("\nMath > ")
        print("\nAnswer:", solve(q))
