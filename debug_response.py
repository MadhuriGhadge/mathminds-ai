"""
Run this script while your backend is running.
It bypasses the frontend completely and shows you EXACTLY what the API returns.

Usage:
  cd E:\madhuri\mathminds
  python debug_response.py

Replace TOKEN and QUESTION below.
"""

import requests
import json

# ── CONFIG ────────────────────────────────────────────────────────────────────
API_URL   = "http://localhost:8000/solve"
TOKEN     = "PASTE_YOUR_FIREBASE_TOKEN_HERE"   # grab from browser devtools
QUESTION  = "what is 9 + 8"
# ─────────────────────────────────────────────────────────────────────────────

headers = {"Authorization": f"Bearer {TOKEN}"}
payload = {
    "text":             QUESTION,
    "model_preference": "agent",
    "session_id":       "debug-session-001",
    "request_id":       "debug-req-001",
}

print(f"\n{'='*60}")
print(f"POST {API_URL}")
print(f"Question: {QUESTION}")
print(f"{'='*60}\n")

try:
    r = requests.post(API_URL, json=payload, headers=headers, timeout=120)
    print(f"HTTP Status: {r.status_code}")
    print(f"\nFull Response JSON:")
    data = r.json()
    print(json.dumps(data, indent=2))

    print(f"\n{'='*60}")
    print(f"status  : {data.get('status')}")
    print(f"answer  : {repr(data.get('answer'))}")
    print(f"source  : {data.get('source')}")
    print(f"explain : {repr(data.get('explanation'))}")
    print(f"error   : {data.get('error')}")
    print(f"{'='*60}\n")

except Exception as e:
    print(f"Request failed: {e}")
