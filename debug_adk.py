
import sys
try:
    import google
    print("google imported")
    print(dir(google))
    
    try:
        import google.adk
        print("google.adk imported")
        print(dir(google.adk))
    except ImportError as e:
        print(f"Failed to import google.adk: {e}")
        
    try:
        from google import adk
        print("from google import adk succeeded")
        print(dir(adk))
    except ImportError as e:
        print(f"Failed to from google import adk: {e}")

except ImportError as e:
    print(f"Failed to import google: {e}")
