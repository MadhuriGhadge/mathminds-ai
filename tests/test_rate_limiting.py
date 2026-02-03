
import sys
import os
import requests
import time

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

BASE_URL = "http://127.0.0.1:8000"

def test_rate_limiting():
    print("Testing Rate Limiting...")
    
    # Ensure service is up
    try:
        resp = requests.get(f"{BASE_URL}/health")
        if resp.status_code != 200:
            print("Server not healthy. Is it running?")
            return
    except requests.exceptions.ConnectionError:
        print("Could not connect to server. Make sure it is running on port 8000.")
        return

    # Send 5 requests (should succeed)
    for i in range(1, 6):
        print(f"Sending request {i}...")
        resp = requests.post(f"{BASE_URL}/solve", json={"input": "1+1"})
        
        if resp.status_code == 200:
            print(f"Request {i}: Success")
        elif resp.status_code == 422:
             print(f"Request {i}: Validation Error (Expected if input invalid, distinct from 429)")
        else:
            print(f"Request {i}: Unexpected status {resp.status_code}")
            print(resp.text)

    # Send 6th request (should fail)
    print("Sending request 6 (Should fail with 429)...")
    resp = requests.post(f"{BASE_URL}/solve", json={"input": "1+1"})
    
    if resp.status_code == 429:
        print("PASS: Request 6 was rate limited (429).")
    else:
        print(f"FAIL: Request 6 status was {resp.status_code}.")
        print(resp.text)

if __name__ == "__main__":
    test_rate_limiting()
