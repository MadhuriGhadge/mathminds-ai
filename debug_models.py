import os
import asyncio
from google import genai
from dotenv import load_dotenv

load_dotenv()

async def list_models():
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("Error: GOOGLE_API_KEY not found.")
        return

    client = genai.Client(api_key=api_key)
    
    print("Listing available models...")
    try:
        # Pager object, need to iterate
        pager = client.models.list()
        for model in pager:
            print(f"Name: {model.name}")
            print(f"  DisplayName: {model.display_name}")
            print(f"  Supported Actions: {model.supported_actions}")
            print("-" * 20)
            
    except Exception as e:
        print(f"Error listing models: {e}")

if __name__ == "__main__":
    asyncio.run(list_models())
