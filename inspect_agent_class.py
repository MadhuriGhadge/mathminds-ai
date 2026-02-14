
import inspect
from google.adk.agents import Agent

print("=== Agent.__init__ ===")
print(inspect.signature(Agent.__init__))
print(Agent.__init__.__doc__)

print("\n=== Agent.run ===")
if hasattr(Agent, 'run'):
    print(inspect.signature(Agent.run))
else:
    print("No run method")

print("\n=== Agent.run_async ===")
if hasattr(Agent, 'run_async'):
    print(inspect.signature(Agent.run_async))
else:
    print("No run_async method")
