import asyncio
import sys
import os
import logging
from datetime import datetime

# Add project root to path
sys.path.append(os.getcwd())

from app.memory.database import DatabaseManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MockCollection:
    def __init__(self):
        self.data = {} # Keyed by session_id for simplicity in this specific test

    def create_indexes(self, indexes):
        pass

    def update_one(self, filter, update, upsert=False):
        session_id = filter.get("session_id")
        if not session_id: return
        
        if session_id not in self.data:
            if upsert:
                # Initialize with setOnInsert
                self.data[session_id] = update.get("$setOnInsert", {})
            else:
                return # No doc to update
        
        doc = self.data[session_id]
        
        # Handle $push
        if "$push" in update:
            for key, val in update["$push"].items():
                if key not in doc: doc[key] = []
                doc[key].append(val)
        
        # Handle $set
        if "$set" in update:
            for key, val in update["$set"].items():
                doc[key] = val

    def find_one(self, filter, projection=None):
        session_id = filter.get("session_id")
        doc = self.data.get(session_id)
        if not doc: return None
        
        # Handle slice projection purely for 'messages'
        if projection and "messages" in projection:
            if "$slice" in projection["messages"]:
                limit = projection["messages"]["$slice"]
                # simplified slice handling
                start = limit if limit < 0 else 0 
                # actually python list slicing for -10 is different. 
                # Mongo slice -10 means "last 10". Python list[-10:] means last 10.
                if limit < 0:
                    doc_copy = doc.copy()
                    doc_copy["messages"] = doc["messages"][limit:]
                    return doc_copy
        return doc

class MockDb:
    def __init__(self):
        self.collections = {"chat_sessions": MockCollection(), "solved_problems": MockCollection()}
    
    def __getitem__(self, key):
        return self.collections[key]

class MockClient:
    def __init__(self, *args, **kwargs):
        self.db = MockDb()
    
    def __getitem__(self, key):
        return self.db
    
    def server_info(self):
        return {"version": "mock"}

async def test_session_lifecycle():
    print("\n--- Test 1: Session Lifecycle (with Mock DB) ---")
    
    # Inject Mock Client
    mock_client = MockClient()
    db = DatabaseManager(client=mock_client)
    # Manually set db property because __init__ does some logic
    db.db = mock_client["mathminds_ai"]
    db.collection = db.db["solved_problems"]
    
    session_id = "test_sess_001"
    print(f"Session ID: {session_id}")
    
    # 1. Create Session
    print("Creating session...")
    created = db.create_session(session_id)
    print(f"Created: {created}")
    
    # 2. Add First User Query (Should update title)
    query1 = "What is the derivatives of sin(x)?"
    print(f"Saving User Query: {query1}")
    db.save_chat_message(session_id, "user", query1)
    
    # Check Title
    doc = db.db["chat_sessions"].find_one({"session_id": session_id})
    print(f"Session Title: {doc.get('title')}")
    assert doc.get('title') == query1, f"Title mismatch. Expected '{query1}', got '{doc.get('title')}'"
    
    # 3. Add AI Response
    response1 = "The derivative of sin(x) is cos(x)."
    print(f"Saving AI Response: {response1}")
    db.save_chat_message(session_id, "model", response1)
    
    # 4. Get History
    history = db.get_chat_history(session_id)
    print(f"History Length: {len(history)}")
    
    assert len(history) == 2, "Should have 2 messages"

    # 5. Add Second User Query (Should NOT update title)
    query2 = "What about cos(x)?"
    db.save_chat_message(session_id, "user", query2)
    
    doc_after = db.db["chat_sessions"].find_one({"session_id": session_id})
    print(f"Session Title (After 2nd Query): {doc_after.get('title')}")
    assert doc_after.get('title') == query1, "Title should not change on second query"
    
    print("\n✅ Verification Passed (Mock Mode)!")

if __name__ == "__main__":
    try:
        asyncio.run(test_session_lifecycle())
    except Exception as e:
        print(f"❌ Test Failed: {e}")
        import traceback
        traceback.print_exc()
