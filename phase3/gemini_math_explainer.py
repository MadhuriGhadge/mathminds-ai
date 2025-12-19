import os
import google.generateveai as genai 

genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

model = genai.GenerativeModel("gemini-1.5-flash")

def explain_math_problem(problem:str)->str:
    """
    takes a math wod problem and returns a step-by-step
    explaination without giving the final numerical solution. 
    """

    prompt = f"""
    you are a helpful math tutor.

    given the following math word problem:    
    \"\"\"{problem}\"\"\"

    explain step by step how to approch and solve the problem.
    - break the solution into logical steps
    - Explain the reasoning clearly 
    - Do Not calculate or provide the final numerical answer 
    - stop before the final computation
    """

    response = model.generate_content(prompt)
    return response.text 

if __name__ == "__main__":
    math_problem = """
A train travels 120 km at a constant speed. If the speed of the train
was increased by 20 km/h, the journey would take 1 hour less.
Find the original speed of the train.
"""

    print(explain_math_problem(math_problem))