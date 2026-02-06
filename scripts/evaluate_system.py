import asyncio
import json
import logging
import time
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.orchestrator import Orchestrator

# Configure Logging
logging.basicConfig(level=logging.ERROR) # Mute app logs
logger = logging.getLogger("evaluator")
logger.setLevel(logging.INFO)

DATASET_PATH = "tests/data/evaluation_dataset.json"

async def run_evaluation():
    print(f"🚀 Starting System Evaluation using {DATASET_PATH}...")
    
    try:
        with open(DATASET_PATH, "r") as f:
            dataset = json.load(f)
    except FileNotFoundError:
        print(f"❌ Dataset not found at {DATASET_PATH}")
        return

    orchestrator = Orchestrator()
    
    results = []
    
    print(f"Loaded {len(dataset)} test cases.\n")
    print(f"{'ID':<10} | {'Category':<15} | {'Model Expected':<15} | {'Model Used':<15} | {'Latency':<10} | {'Status'}")
    print("-" * 90)

    for case in dataset:
        case_id = case["id"]
        category = case["category"]
        text_input = case["input"]
        expected_model = case.get("expected_model")
        expected_keywords = case.get("expected_keywords", [])
        expected_error = case.get("expected_error", False)

        start_ts = time.time()
        
        # Call System
        try:
            response = await orchestrator.process_problem(text=text_input)
            latency = time.time() - start_ts
            
            # Checks
            status = "PASS"
            fail_reasons = []

            # 1. Error Check
            if expected_error:
                if "error" not in response and response.get("status") == "success":
                   status = "FAIL"
                   fail_reasons.append("Expected error, got success")
            else:
                if response.get("status") == "error":
                    status = "FAIL"
                    fail_reasons.append(f"Error: {response.get('error') or response.get('error_msg')}")
                
                # 2. Answer Check
                answer_text = str(response.get("answer", "") or "")
                model_used = response.get("metadata", {}).get("model_used", "unknown")
                
                # Check keywords
                for kw in expected_keywords:
                    if kw.lower() not in answer_text.lower():
                        status = "FAIL"
                        fail_reasons.append(f"Missing keyword '{kw}'")
                        break
                
                # 3. Model Check (Loose check, just warning if mismatch often)
                # Note: Qwen might be 'qwen2.5-math' or similar in metadata
                if expected_model and expected_model not in model_used:
                     # Don't fail hard on model swap if answer is correct, but note it
                     # status = "WARN" # Optional
                     pass

            # Print Row
            model_display = response.get("metadata", {}).get("model_used", "N/A")
            latency_display = f"{latency:.2f}s"
            
            row_color = ""
            if status == "FAIL":
                row_color = "❌ "
            else:
                row_color = "✅ "

            print(f"{row_color}{case_id:<8} | {category:<15} | {expected_model or 'Any':<15} | {model_display:<15} | {latency_display:<10} | {status}")
            
            if status == "FAIL":
                print(f"   Details: {fail_reasons}")
                print(f"   Output: {answer_text[:100]}...")

            results.append({
                "id": case_id,
                "latency": latency,
                "status": status,
                "model_used": model_display
            })

        except Exception as e:
            print(f"❌ {case_id:<8} | CRITICAL ERROR: {e}")
    
    # Summary
    print("-" * 90)
    passed = len([r for r in results if r["status"] == "PASS"])
    total = len(dataset)
    print(f"🏁 Evaluation Complete. Passed: {passed}/{total} ({passed/total*100:.1f}%)")

if __name__ == "__main__":
    asyncio.run(run_evaluation())
