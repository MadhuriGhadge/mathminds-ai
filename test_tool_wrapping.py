
from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool

def my_tool(x: int) -> int:
    """doubles x"""
    return x * 2

try:
    print("Trying to init LlmAgent with raw function...")
    agent = LlmAgent(
        name="test",
        model="gemini-flash-latest",
        instruction="test",
        tools=[my_tool]
    )
    print("Success! LlmAgent accepted raw function.")
except Exception as e:
    print(f"Failed with raw function: {e}")

try:
    print("\nTrying to init LlmAgent with FunctionTool...")
    agent = LlmAgent(
        name="test",
        model="gemini-flash-latest",
        instruction="test",
        tools=[FunctionTool(my_tool)]
    )
    print("Success! LlmAgent accepted FunctionTool.")
except Exception as e:
    print(f"Failed with FunctionTool: {e}")
