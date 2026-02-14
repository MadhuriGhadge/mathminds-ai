
try:
    from google.adk.agents import Agent
    print("Agent class found in google.adk.agents")
except ImportError:
    print("Agent class NOT found in google.adk.agents")
    
try:
    from google.adk.agents import LlmAgent
    print("LlmAgent class found in google.adk.agents")
except ImportError:
    print("LlmAgent class NOT found in google.adk.agents")
