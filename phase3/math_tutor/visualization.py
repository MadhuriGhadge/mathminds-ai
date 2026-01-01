import sympy as sp
import numpy as np
import plotly.graph_objects as go
from math_tools import normalize_expression


def plot_expression(expr_str: str):
    x = sp.symbols('x')

    # Normalize expression (x^2 → x**2, 5x → 5*x)
    expr_str = normalize_expression(expr_str)
    expr = sp.sympify(expr_str)

    f = sp.lambdify(x, expr, "numpy")

    x_vals = np.linspace(-10, 10, 400)
    y_vals = f(x_vals)

    fig = go.Figure()

    # Plot function
    fig.add_trace(
        go.Scatter(
            x=x_vals,
            y=y_vals,
            mode="lines",
            name=f"y = {expr}"
        )
    )

    # Find and plot roots
    roots = sp.solve(expr)
    for r in roots:
        if r.is_real:
            fig.add_trace(
                go.Scatter(
                    x=[float(r)],
                    y=[0],
                    mode="markers",
                    marker=dict(size=10, color="red"),
                    name=f"Root at x = {r}"
                )
            )

    fig.update_layout(
        title="Function Visualization",
        xaxis_title="x",
        yaxis_title="y",
        template="plotly_white"
    )

    return fig
