from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

# Request model
class MathRequest(BaseModel):
    problem: str

# Endpoint
@app.post("/solve")
def solve_math(request: MathRequest):
    # Placeholder solution logic (we’ll replace later)
    return {
        "original_problem": request.problem,
        "solution": f"Placeholder solution for: {request.problem}"
    }
