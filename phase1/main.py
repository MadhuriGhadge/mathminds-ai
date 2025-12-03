from fastapi import FastAPI, UploadFile, File
from pydantic import BaseModel

app = FastAPI()

class MathQuery(BaseModel):
    problem: str

@app.post("/solve_text")
def solve_text(data: MathQuery):
    return {"solution": f"Received text: {data.problem}"}

@app.post("/solve_image")
def solve_image(file: UploadFile = File(...)):
    return {"solution": f"Received image: {file.filename}"}
