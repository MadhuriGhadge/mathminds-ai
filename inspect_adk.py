
import os
import sys
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from google.adk.agents import LlmAgent
    import inspect
    
    print("=== LlmAgent.__init__ ===")
    print(inspect.signature(LlmAgent.__init__))
    print(LlmAgent.__init__.__doc__)
    
    print("\n=== LlmAgent.run ===")
    if hasattr(LlmAgent, 'run'):
        print(inspect.signature(LlmAgent.run))
        print(LlmAgent.run.__doc__)
    else:
        print("No run method")

    print("\n=== google.adk.runners.Runner ===")
    try:
        from google.adk.runners import Runner
        print(inspect.signature(Runner.__init__))
        print(Runner.__init__.__doc__)
        
        print("\n=== Runner.run_async ===")
        if hasattr(Runner, 'run_async'):
             print(inspect.signature(Runner.run_async))
             print(Runner.run_async.__doc__)
    except ImportError:
        print("Could not import google.adk.runners.Runner")

    print("\n=== google.adk.model.Model ===")
    print("\n=== google.adk.sessions.in_memory_session_service.InMemorySessionService ===")
    try:
        from google.adk.sessions.in_memory_session_service import InMemorySessionService
        print(dir(InMemorySessionService))
        print(inspect.signature(InMemorySessionService.create_session))
    except ImportError:
         print("Could not import google.adk.sessions.in_memory_session_service.InMemorySessionService")
    except Exception as e:
        print(f"Error inspecting InMemorySessionService: {e}")
         
    try:
        import google.genai.types
        print("\n=== google.genai.types ===")
        print("google.genai.types found")
    except ImportError:
        print("Could not import google.genai.types")

except ImportError as e:
    print(f"Failed to import: {e}")
except Exception as e:
    print(f"Error: {e}")
