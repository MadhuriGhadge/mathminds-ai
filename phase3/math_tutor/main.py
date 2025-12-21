"""
from agent import run_agent

if __name__ == "__main__":
    print(run_agent("Explain the concept of derivatives"))
    print(run_agent("Solve the equation x^2 - 5x + 6 = 0"))
    print(run_agent("Convert an image of integral of x squared"))
"""

from agent import run_agent_with_image

if __name__ == "__main__":
    result = run_agent_with_image(
        r"E:\madhuri\mathminds-ai\phase3\math_tutor\sample_math.jpg"
    )
    print(result)

