
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

print("Verifying Phase 4 Implementation...")

try:
    import gradio_demo
    print("✅ Gradio Demo imported successfully (Syntax Check Passed).")
except ImportError as e:
    print(f"⚠️ Import Error for Gradio Demo (Likely missing dependencies): {e}")
except Exception as e:
    print(f"❌ Syntax/Runtime Error in Gradio Demo: {e}")

try:
    from app.tools.selenium_scraper import SeleniumScraper
    print("✅ SeleniumScraper imported successfully (Syntax Check Passed).")
except ImportError as e:
    print(f"⚠️ Import Error for SeleniumScraper (Likely missing dependencies): {e}")
except Exception as e:
    print(f"❌ Syntax/Runtime Error in SeleniumScraper: {e}")

print("\nVerification Complete.")
