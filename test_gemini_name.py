from google.genai import Client
from app.core.settings import settings

client = Client(api_key=settings.GOOGLE_API_KEY)

print("Searching for Flash models...")
try:
    models = client.models.list()
    for m in models:
        if "flash" in m.name.lower():
            print(f"Name: {m.name}")
except Exception as e:
    print(f"List failed: {e}")
