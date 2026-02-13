
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

print("Verifying Phase 2 Implementation...")

try:
    from app.models.vertex_gemini import VertexGeminiModel
    print("✅ VertexGeminiModel imported successfully.")
except ImportError as e:
    print(f"⚠️ Import Error for VertexGeminiModel: {e}")
except Exception as e:
    print(f"❌ Error in VertexGeminiModel: {e}")

try:
    from app.database.firestore_client import FirestoreClient
    print("✅ FirestoreClient imported successfully.")
except ImportError as e:
    print(f"⚠️ Import Error for FirestoreClient: {e}")
except Exception as e:
    print(f"❌ Error in FirestoreClient: {e}")

print("\nVerification Complete.")
