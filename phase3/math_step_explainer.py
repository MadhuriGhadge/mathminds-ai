import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

def explain_math_problem(problem: str) -> str:
    """
    Generates a step-by-step explanation for a math word problem
    without providing the final numerical answer.
    """

    prompt = f"""
You are a helpful and careful math tutor.

Given the following math word problem:
\"\"\"{problem}\"\"\"

Explain step by step how to approach and solve the problem.

Rules:
- Break the solution into clear logical steps
- Explain the reasoning behind each step
- Do NOT compute or reveal the final numerical answer
- Stop before the final calculation
"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )

    return response.text


if __name__ == "__main__":
    math_problem = """
A tank is filled by two pipes. Pipe A can fill the tank in 6 hours,
and Pipe B can fill it in 4 hours. If both pipes are opened together
but Pipe B is closed 1 hour before the tank is full, how long does
it take to fill the tank?
"""

    explanation = explain_math_problem(math_problem)
    print(explanation)
