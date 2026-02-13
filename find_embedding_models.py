import os
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

print("Available models:")
for model in genai.list_models():
    if "gemini" in model.name:
        print(f"  {model.name:50}  {model.display_name}")