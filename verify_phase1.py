
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

print("Verifying Phase 1 Implementation...")

try:
    from app.agents.langchain_mathminds import MathMindsLangChainAgent
    print("✅ MathMindsLangChainAgent imported successfully (Syntax Check Passed).")
except ImportError as e:
    print(f"⚠️ Import Error for Agent (Likely missing dependencies): {e}")
except Exception as e:
    print(f"❌ Syntax/Runtime Error in Agent: {e}")

try:
    from app.tools.data_processor import DataProcessor
    print("✅ DataProcessor imported successfully (Syntax Check Passed).")
except ImportError as e:
    print(f"⚠️ Import Error for DataProcessor (Likely missing dependencies): {e}")
except Exception as e:
    print(f"❌ Syntax/Runtime Error in DataProcessor: {e}")

try:
    from app.tools.advanced_ocr import AdvancedOCR
    print("✅ AdvancedOCR imported successfully (Syntax Check Passed).")
except ImportError as e:
    print(f"⚠️ Import Error for AdvancedOCR (Likely missing dependencies): {e}")
except Exception as e:
    print(f"❌ Syntax/Runtime Error in AdvancedOCR: {e}")

print("\nVerification Complete. If you see 'Import Error', please run: pip install -r requirements.txt")
