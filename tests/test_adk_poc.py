
import asyncio
import os
import sys
import logging
from dotenv import load_dotenv

# Fix path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
load_dotenv()

logging.basicConfig(level=logging.INFO)

try:
    from google.adk.agents import LlmAgent
    from google.adk.runners import Runner
    from google.adk.sessions.in_memory_session_service import InMemorySessionService
    from google.genai import types
except ImportError as e:
    print(f"Import Error: {e}")
    sys.exit(1)

async def main():
    print("Initializing components...")
    
    # 1. Agent
    # Note: LlmAgent arguments might strictly be pydantic fields.
    # If 'model' is expected to be a string alias, this works.
    agent = LlmAgent(
        name="MathTest",
        model="gemini-2.5-flash",
        instruction="You are a helpful math assistant." 
    )
    
    # 2. Session Service
    session_service = InMemorySessionService()
    
    # 3. Runner
    # Assuming Runner takes agent and session_service. 
    # If it needs 'model' client explicitly, we might fail here.
    try:
        runner = Runner(agent=agent, app_name="MathMindsPoC", session_service=session_service)
    except TypeError as e:
        print(f"Runner init failed: {e}")
        # Maybe it takes arguments differently?
        return

    print("Setting up session...")
    session_id = "poc_session"
    user_id = "poc_user"

    try:
        await session_service.create_session(
            app_name="MathMindsPoC",
            user_id=user_id,
            session_id=session_id
        )
    except Exception as e:
        print(f"Session creation failed: {e}")
        return

    print("Running agent...")

    try:
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=types.Content(
                role="user",
                parts=[types.Part.from_text(text="What is 10 * 10?")]
            )
        ):
            # Print the event to see structure
            print(f"Event: {type(event)}")
            if hasattr(event, 'content') and event.content:
                 for part in event.content.parts:
                     if part.text:
                         print(f"Text: {part.text}")
            
    except Exception as e:
        print(f"Run Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
