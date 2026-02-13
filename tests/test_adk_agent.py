
import asyncio
import os
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import Google ADK components
from google.adk.agents.llm_agent import LlmAgent
from google.adk.models.google_llm import Gemini
from google.adk.tools.function_tool import FunctionTool
from google.adk.runners import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.genai import types

# Define a simple tool
def calculator(a: int, b: int, op: str) -> int:
    """Performs simple arithmetic operations.
    
    Args:
        a: The first number.
        b: The second number.
        op: The operation ('+', '-', '*', '/').
    """
    logger.info(f"Calculator called with a={a}, b={b}, op={op}")
    if op == '+':
        return a + b
    elif op == '-':
        return a - b
    elif op == '*':
        return a * b
    elif op == '/':
        return int(a / b)
    return 0

async def main():
    print("Initializing Google ADK Agent...")
    
    # 1. Create Model
    # Ensure GOOGLE_API_KEY is set in .env
    model = Gemini(model="gemini-2.5-flash")
    
    # 2. Create Tools
    calc_tool = FunctionTool(calculator)
    
    # 3. Create Agent
    agent = LlmAgent(
        name="math_helper",
        model=model,
        tools=[calc_tool],
        instruction="You are a helpful math assistant. Use the calculator tool for computations."
    )
    
    # 4. Create Services
    session_service = InMemorySessionService()
    
    # 5. Create Runner
    runner = Runner(
        app_name="mathminds_adk_test",
        agent=agent,
        session_service=session_service
    )
    
    # 6. Run Agent
    user_id = "test_user"
    session_id = "test_session"
    prompt = "Calculate 15 * 12 then add 50."
    
    print(f"\nUser: {prompt}")
    
    # Creating a new session explicitly if needed, but runner might handle it.
    # Runner.run requires session to exist? define user_id and session_id.
    # InMemorySessionService usually auto-creates if logic allows, checking Runner code...
    # Runner.run check: session_service.get_session returns None -> ValueError "Session not found"
    # So we must create session first.
    
    session = await session_service.create_session(
        app_name="mathminds_adk_test",
        user_id=user_id,
        session_id=session_id
    )
    
    print("Session created. Running agent...")
    
    # Using run_async for better control
    response_text = ""
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=types.Content(role="user", parts=[types.Part.from_text(prompt)])
    ):
        # Inspect event types
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.text:
                    print(f"Agent partial: {part.text}")
                    response_text += part.text
                if part.function_call:
                    print(f"Tool Call: {part.function_call.name}({part.function_call.args})")
                if part.function_response:
                    print(f"Tool Result: {part.function_response.response}")
                    
    print(f"\nFinal Response: {response_text}")

if __name__ == "__main__":
    asyncio.run(main())
