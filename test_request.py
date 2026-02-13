import requests
import json
import time

url = "http://localhost:8001/solve"
# Read from payload.json
with open("payload.json", "r") as f:
    payload = json.load(f)

headers = {
    "Content-Type": "application/json"
}

start_time = time.time()
try:
    print(f"Sending request to {url}...")
    response = requests.post(url, json=payload, headers=headers)
    print(f"Status Code: {response.status_code}")
    print(f"Duration: {time.time() - start_time:.2f}s")
    print("Response Body:")
    print(response.text)
except Exception as e:
    print(f"Error: {e}")
