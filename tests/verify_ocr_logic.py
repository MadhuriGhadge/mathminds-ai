import sys
import os
import unittest
from unittest.mock import MagicMock, patch
from PIL import Image, ImageDraw
import io

# Mock paddleocr in sys.modules to prevent real import attempt
# This avoids potential hangs if the library tries to download models or isn't installed
sys.modules['paddleocr'] = MagicMock()

# Add app to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.ocr import OCRProcessor

class TestOCRLogic(unittest.TestCase):
    def test_preprocessing_converts_to_binary(self):
        """Verify preprocessing steps produce a binary-like image."""
        ocr = OCRProcessor()
        
        # Create a test image (RGB, Red background with text)
        img = Image.new('RGB', (100, 50), color = (255, 0, 0))
        d = ImageDraw.Draw(img)
        d.text((10,10), "Test", fill=(0,0,0))
        
        # Run preprocessing
        processed = ocr._preprocess_image(img)
        
        # Check mode is '1' (binary)
        # Note: Depending on environment, it might be 'L' if something failed, 
        # but my code explicitly does .point(..., '1')
        self.assertEqual(processed.mode, '1', "Image should be converted to binary mode '1'")
        print("\n[PASS] Preprocessing converted image to binary mode.")

    def test_structure_preservation(self):
        """Verify that multi-line text is joined with newlines."""
        ocr = OCRProcessor()
        
        # Mock the internal OCR engine
        mock_ocr_engine = MagicMock()
        # Mock result structure: [ [ [box], ("Text", score) ], ... ] wrapped in outer list
        # PaddleOCR returns a list of results (one per image), we perform on 1 image, so result[0] is the list of lines.
        mock_lines = [
            (None, ("Line 1", 0.99)),
            (None, ("Line 2", 0.98)),
            (None, ("Line 3", 0.97))
        ]
        mock_ocr_engine.ocr.return_value = [mock_lines]
        
        # Inject mock
        ocr.ocr = mock_ocr_engine
        ocr._enabled = True
        
        # Create dummy image bytes
        img = Image.new('RGB', (100, 100))
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        img_bytes = buf.getvalue()
        
        # Run process
        result = ocr._process_image_data(img_bytes)
        
        expected = "Line 1\nLine 2\nLine 3"
        self.assertEqual(result, expected, "Result text should preserve newlines")
        print(f"\n[PASS] Structure preservation verified. Output:\n{result}")

if __name__ == '__main__':
    unittest.main()
