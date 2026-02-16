
import sys
import os
sys.path.insert(0, os.getcwd())

import base64
import io
from PIL import Image, ImageDraw
from app.core.ocr import OCRProcessor

def create_test_image_b64(text: str) -> str:
    img = Image.new('RGB', (400, 100), color=(255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((10, 40), text, fill=(0, 0, 0))
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()

def test_ocr_direct():
    print("Initializing OCRProcessor...")
    ocr = OCRProcessor()
    
    text = "Hello OCR World"
    b64 = create_test_image_b64(text)
    
    print(f"Extracting text from image with '{text}'...")
    result = ocr.extract_text(image_data=b64)
    
    print(f"Result: {result}")
    
    if text in result:
        print("SUCCESS: OCR worked correctly.")
    else:
        print("FAILURE: Text not found.")

if __name__ == "__main__":
    test_ocr_direct()
