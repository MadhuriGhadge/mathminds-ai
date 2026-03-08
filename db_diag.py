import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

mongo_uri = os.getenv("MONGO_URI")
client = MongoClient(mongo_uri)
db = client.mathminds_db
# FIXED COLLECTION NAME
sessions = db.chat_sessions

print("LAST 3 SESSIONS:")
for s in sessions.find().sort("created_at", -1).limit(3):
    print(f"Session: {s.get('session_id')} | User: {s.get('user_id')}")
    print(f"Title: {s.get('title')}")
    msgs = s.get("messages", [])
    print(f"Messages Count: {len(msgs)}")
    for m in msgs[-10:]:
        print(f"  [{m.get('role')}] {m.get('content')[:100]} (RID: {m.get('request_id')})")
    print("-" * 20)
