
import json
try:
    with open('chat_history.json') as f:
        data = json.load(f)
    last_session_id = sorted(data.keys(), key=lambda k: data[k].get('created_at', 0))[-1]
    print(f"Session: {last_session_id}")
    messages = data[last_session_id]['messages']
    print(f"Total messages: {len(messages)}")
    for i, m in enumerate(messages):
        print(f"Index {i}: Role: {m['role']}")
        print(f"  Sent to API: {m.get('sent_to_api')}")
        print(f"  Content: {repr(m['content'])[:100]}...")
except Exception as e:
    print(f"Error: {e}")
