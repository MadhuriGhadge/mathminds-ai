import requests
import json
import time

url = "http://localhost:8000/solve"
payload = {
    "text": "what is 2+2?",
    "session_id": "test_session",
    "request_id": "test_rid_" + str(time.time())
}

print(f"Calling {url}...")
headers = {"Authorization": "Bearer mock_token_123"}
try:
    with requests.post(url, json=payload, headers=headers, stream=True, timeout=30) as r:
        print(f"Status: {r.status_code}")
        for chunk in r.iter_content(chunk_size=1, decode_unicode=True):
            if chunk:
                print(chunk, end="", flush=True)
except Exception as e:
    print(f"\nFAILED: {e}")
