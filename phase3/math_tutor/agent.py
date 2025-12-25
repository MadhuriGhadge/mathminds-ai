from gemini_client import get_client
from schemas import function_declarations
from math_tools import convert_image_to_latex
from utils import load_image_bytes

client = get_client()
   
def image_to_text(image_path: str) -> str:
    image_bytes = load_image_bytes(image_path)

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[
            {
                "role": "user",
                "parts": [
                    {"text": "Extract the math expression from this image as LaTeX."},
                    {
                        "inline_data": {
                            "mime_type": "image/jpeg",
                            "data": image_bytes
                        }
                    }
                ]
            }
        ]
    )

    return response.text


def run_agent(user_input: str):
    """
    Normal text-based agent with tools
    """
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=user_input
    )

    return response.text


def run_agent_with_image(image_path: str):
    """
    Pipeline:
    Image -> Extract text -> Run agent
    """
    extracted_text = image_to_text(image_path)
    return run_agent(extracted_text)


