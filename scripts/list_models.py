import os
from google import genai
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    print("No API Key found")
    exit(1)

client = genai.Client(api_key=api_key)

try:
    print("Listing models...")
    # The SDK might have a slightly different list method depending on version
    # Trying standard approach
    for m in client.models.list(config={"page_size": 100}):
        # Debug: print available fields if needed, or just list all
        # To avoid noise, let's just print names.
        print(f"Model: {m.name}")
        # print(dir(m)) # Uncomment if desperate
except Exception as e:
    print(f"Error: {e}")
