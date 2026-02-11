import asyncio
import sys
import os
import base64

# Add project root to path
sys.path.append(os.getcwd())

print("Importing VisionAnalyzer... (This may take a moment)")
from app.tools.vision_analyzer import VisionAnalyzer
print("Import complete.")

def test_vision():
    print("\n--- Test: Vision Analyzer (YOLO) ---")
    
    analyzer = VisionAnalyzer()
    
    # Find all image files
    # extensions = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
    # image_files = [f for f in os.listdir(".") if os.path.splitext(f)[1].lower() in extensions]
    image_files = ["balls.jpg"]
    
    if not os.path.exists(image_files[0]):
         print(f"Error: {image_files[0]} not found.")
         return
    
    if not image_files:
        print("No image files found in directory.")
        return

    print(f"Found {len(image_files)} images: {image_files}")
    
    for test_img in image_files:
        print(f"\nProcessing: {test_img}")
        try:
            with open(test_img, "rb") as f:
                img_data = base64.b64encode(f.read()).decode("utf-8")
                
            query = "count the orbs"
            result = analyzer.analyze(img_data, query)
            
            if result.get("status") == "success":
                mode = result.get("vision_mode", "unknown")
                print(f"  Vision Mode: {mode}")
                
                if mode == "quantitative":
                    quant = result.get("quantitative_analysis", {})
                    objects = quant.get("objects", {})
                    print(f"  Total Objects: {quant.get('total_objects')}")
                    print(f"  Avg Confidence: {quant.get('avg_confidence')}")
                    if objects:
                        print("  Objects Detected:")
                        for key, count in objects.items():
                            print(f"    - {key}: {count}")
                    else:
                        print("    (No specific objects detected)")
                else:
                     print("  Mode is qualitative (no YOLO run or no objects found).")
            else:
                print("  Error:", result.get("error"))
        except Exception as e:
            print(f"  Failed to process {test_img}: {e}")

if __name__ == "__main__":
    test_vision()
