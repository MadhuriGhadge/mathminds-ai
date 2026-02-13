
print("Start")
try:
    import app.tools.web_scraper
    print("Imported WebScraper")
except Exception as e:
    print(f"Failed WebScraper: {e}")

try:
    import app.tools.vision_analyzer
    print("Imported VisionAnalyzer")
except Exception as e:
    print(f"Failed VisionAnalyzer: {e}")

try:
    from app.core.orchestrator import Orchestrator
    print("Imported Orchestrator")
    o = Orchestrator()
    print("Instantiated Orchestrator")
except Exception as e:
    print(f"Failed Orchestrator: {e}")
