"""
Streamlit UI for MathMinds AI.

Responsibility: Orchestrate user input and display results.
Keeps UI separate from solving logic (agent + solver).
"""
from typing import Any, Dict
import streamlit as st
from agent import solve_problem

st.set_page_config(page_title="MathMinds AI", layout="centered")

TITLE = "MathMinds AI"
SUBTITLE = "Your Personal Quantitative Assistant"

def render_result(result: Dict[str, Any]) -> None:
    """
    Render the JSON contract returned by the agent in a clean UI.
    """
    mode = result.get("mode", "unknown")
    equations = result.get("equations", [])
    solution = result.get("solution", None)
    explanation = result.get("explanation", "")

    st.markdown(f"### Mode: {'🧮 Symbolic Solution' if mode == 'symbolic' else '🤖 AI Reasoning Solution'}")
    st.write("**Extracted Equations:**")
    for eq in equations:
        st.code(eq)

    st.write("**Solution:**")
    st.json(solution)

    st.text_area("Explanation", explanation, height=400)


def main() -> None:
    st.title(TITLE)
    st.subheader(SUBTITLE)

    st.write("Enter a math problem in natural language. MathMinds will attempt a symbolic solution first (SymPy). If symbolic solving fails, the assistant will fall back to AI reasoning.")

    problem_input = st.text_area("Problem", height=200, placeholder="e.g. Find x and y if x + y = 10 and x - y = 2")
    solve_button = st.button("Solve")

    if solve_button:
        if not problem_input.strip():
            st.warning("Please enter a problem.")
            return

        # Show spinner while orchestrator runs
        with st.spinner("Thinking..."):
            try:
                result = solve_problem(problem_input)
            except Exception as e:
                # Catch unexpected errors to keep UI responsive.
                st.error("An unexpected error occurred. See details below.")
                st.exception(e)
                return

        render_result(result)


if __name__ == "__main__":
    main()