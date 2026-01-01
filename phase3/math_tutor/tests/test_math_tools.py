from math_tutor.math_tools import solve_mathematical_problem

def test_quadratic_solver():
    result = solve_mathematical_problem("x^2 - 5x + 6")
    assert "2" in result
    assert "3" in result
