import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

def generate_text_with_gemini(prompt_text: str):
    """
    Generates text from the Gemini model based on a prompt.
    """
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt_text
    )
    return response.text


if __name__ == "__main__":
    prompt = """
    A train travels 120 km at a constant speed. If the speed of the train
    was increased by 20 km/h, the journey would take 1 hour less.
    Find the original speed of the train.
    """
    print("Prompt:", prompt, "\n")
    print(generate_text_with_gemini(prompt))
