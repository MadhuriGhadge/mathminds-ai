
import json
import os

HISTORY_FILE = 'chat_history.json'

def debug():
    if not os.path.exists(HISTORY_FILE):
        print("File not found")
        return

    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        last_sid = sorted(data.keys(), key=lambda k: data[k].get('created_at', 0))[-1]
        sess = data[last_sid]
        print(f"Session: {last_sid} (Title: {sess.get('title')})")
        print(f"Total messages: {len(sess['messages'])}")
        
        for i, m in enumerate(sess['messages']):
            print(f"[{i}] {m['role'].upper()}: {repr(m['content'])[:80]}...")
            if 'metadata' in m:
                print(f"    Metadata keys: {list(m['metadata'].keys())}")
            
    except Exception as e:
        print(f"CRITICAL ERROR reading history: {e}")

if __name__ == "__main__":
    debug()
