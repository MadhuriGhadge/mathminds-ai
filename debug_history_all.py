
import json
try:
    with open('chat_history.json') as f:
        data = json.load(f)
    print(f"Total sessions: {len(data)}")
    for sid, sess in data.items():
        print(f"Session {sid}: {sess.get('title', 'Untitled')} ({len(sess['messages'])} msgs)")
        for m in sess['messages']:
            if m['role'] == 'assistant':
                 print(f"  [FOUND ASSISTANT MSG in {sid}] Content: {repr(m['content'])[:50]}")
except Exception as e:
    print(f"Error: {e}")
