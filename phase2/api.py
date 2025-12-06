from fastapi import FastAPI
from pydantic import BaseModel
from database import problems_collection
from datetime import datetime

app = FastAPI()

class ProblemInput(BaseModel):
    user_id: str
    problem: str

@app.post("/save-problem")
def save_problem(data: ProblemInput):
    new_record = {
        "user_id": data.user_id,
        "problem": data.problem,
        "created_at":datetime.utcnow()
    }
    problems_collection.insert_one(data.dict())
    return {"status": "success", "message": "Problem saved successfully!"}


@app.get("/problems/{user_id}")
def get_problems(user_id: str):
    records = list(problems_collection.find({"user_id": user_id}, {"_id":0}))
    return {"user_id":user_id, "problems": records}

