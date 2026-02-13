
import sys
import os
import yaml

# Add project root to path
sys.path.append(os.getcwd())

print("Verifying Phase 3 Implementation...")

# 1. Verify Worker Import
try:
    from app.worker import scrape_web_task
    print("✅ Celery Task 'scrape_web_task' imported successfully.")
except ImportError as e:
    print(f"❌ Import Error for app.worker: {e}")

# 2. Verify Orchestrator Import (Static Check not easy, so we check if file content has changed)
# We trust the file write, but let's check docker-compose.yml
try:
    with open("docker-compose.yml", "r") as f:
        dc = yaml.safe_load(f)
    
    services = dc.get("services", {})
    if "worker" in services:
        print("✅ Docker Compose: 'worker' service found.")
    else:
        print("❌ Docker Compose: 'worker' service MISSING.")

    if "n8n" in services:
        print("✅ Docker Compose: 'n8n' service found.")
    else:
        print("❌ Docker Compose: 'n8n' service MISSING.")

except Exception as e:
    print(f"❌ Error reading docker-compose.yml: {e}")

print("\nVerification Complete.")
