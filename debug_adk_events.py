"""
Run this script STANDALONE — no FastAPI needed.
It directly invokes the ADK agent and prints every single event it emits,
so we can see exactly what is_final_response() returns and what text we get.

Usage:
  cd E:\madhuri\mathminds
  python debug_adk_events.py
"""

import asyncio
import sys
import os
sys.path.insert(0, os.getcwd())

from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.genai import types
from dotenv import load_dotenv
load_dotenv()

QUESTION = "what is 9 + 8"

async def main():
    from app.core.settings import settings

    agent = Agent(
        name="math_minds_core",
        model="gemini-2.5-flash",
        tools=[],
        instruction="You are a math assistant. Answer concisely."
    )

    session_service = InMemorySessionService()
    runner = Runner(
        app_name="mathminds_debug",
        agent=agent,
        session_service=session_service
    )

    await session_service.create_session(
        app_name="mathminds_debug",
        user_id="debug_user",
        session_id="debug_session"
    )

    print(f"\nQuestion: {QUESTION}\n{'='*60}")

    all_text   = ""
    final_text = ""
    event_num  = 0

    async for event in runner.run_async(
        user_id="debug_user",
        session_id="debug_session",
        new_message=types.Content(role="user", parts=[types.Part.from_text(text=QUESTION)])
    ):
        event_num += 1
        event_type = type(event).__name__
        author     = getattr(event, "author", "N/A")

        # Check is_final_response
        has_ifr = hasattr(event, "is_final_response") and callable(event.is_final_response)
        is_final = event.is_final_response() if has_ifr else "method missing"

        print(f"\n[Event #{event_num}]")
        print(f"  type              : {event_type}")
        print(f"  author            : {author}")
        print(f"  is_final_response : {is_final}")
        print(f"  has content       : {bool(event.content)}")

        if event.content and event.content.parts:
            for i, part in enumerate(event.content.parts):
                print(f"  part[{i}].text          : {repr(part.text)}")
                print(f"  part[{i}].function_call : {bool(getattr(part, 'function_call', None))}")
                print(f"  part[{i}].function_resp : {bool(getattr(part, 'function_response', None))}")
                if part.text:
                    all_text += part.text
                    if is_final is True:
                        final_text += part.text
                    if author == "math_minds_core":
                        final_text += part.text

    print(f"\n{'='*60}")
    print(f"Total events       : {event_num}")
    print(f"all_text (fallback): {repr(all_text)}")
    print(f"final_text         : {repr(final_text)}")
    print(f"RESULT WOULD BE    : {repr((final_text or all_text).strip())}")

asyncio.run(main())
