
import sys
import os

print(f"Python Executable: {sys.executable}")
print(f"Python Version: {sys.version}")
print(f"Sys Path: {sys.path}")

try:
    import langchain
    print(f"LangChain Version: {langchain.__version__}")
    print(f"LangChain Path: {langchain.__file__}")
except ImportError as e:
    print(f"ImportError: {e}")
except Exception as e:
    print(f"Error: {e}")

# Verify Agent Import
try:
    from app.agents.langchain_mathminds import MathMindsLangChainAgent
    print("✅ MathMindsLangChainAgent imported.")
except ImportError as e:
    print(f"Agent Import Failed: {e}")
