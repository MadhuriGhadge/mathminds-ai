import sys
import os
import unittest
import base64
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.input_processor import InputProcessor, InputType
from app.core.ocr import OCRProcessor

class TestOCR(unittest.TestCase):
    def setUp(self):
        # We process input which instantiates OCRProcessor
        # We need to mock OCRProcessor internal paddleocr to avoid download
        self.processor = InputProcessor()
        
    @patch('app.core.ocr.PaddleOCR')
    @patch('app.core.ocr.Image') # Mock Pillow Image
    def test_base64_ocr_success(self, mock_image, mock_paddle):
        # Setup mocks
        mock_ocr_instance = MagicMock()
        mock_paddle.return_value = mock_ocr_instance
        
        # Mock OCR result: list of lines, where each line is list of words, where word is [box, [text, score]]
        # PaddleOCR result format is complex: [ [ [ [x,y]..], ("text", score) ] ... ] ]
        # Our code expects: result[0][i][1][0] is text
        mock_ocr_instance.ocr.return_value = [[
            [None, ("1+1", 0.99)],
            [None, ("=", 0.98)],
            [None, ("?", 0.95)]
        ]]
        
        # Mock valid image check
        mock_img_instance = MagicMock()
        # Ensure format is allowed
        type(mock_img_instance).format = unittest.mock.PropertyMock(return_value='PNG')
        mock_image.open.return_value = mock_img_instance
        
        # Create a dummy base64 string (valid format but dummy content)
        b64_str = "data:image/png;base64," + base64.b64encode(b"dummydata").decode('utf-8')
        
        # Inject our mocked ocr processor into the input processor 
        # (Since InputProcessor initializes it in init, we can replace it OR verify usage)
        # Better: let's just patch OCRProcessor class used by InputProcessor? 
        # But InputProcessor already instantiated in setUp.
        # Let's replace the instance.
        
        ocr_proc = OCRProcessor()
        ocr_proc.ocr = mock_ocr_instance # Inject mock paddle
        ocr_proc._enabled = True
        self.processor.ocr_processor = ocr_proc
        
        result = self.processor.process(b64_str)
        
        self.assertTrue(result.is_valid)
        self.assertEqual(result.input_type, InputType.BASE64_IMAGE)
        self.assertEqual(result.cleaned_content, "1+1 = ?")
        
    def test_invalid_image_data(self):
         # invalid base64
         result = self.processor.process("data:image/png;base64,INVALID_STUFF")
         self.assertFalse(result.is_valid)
         self.assertEqual(result.input_type, InputType.BASE64_IMAGE) # Detects type but fails processing
         self.assertIn("Failed to process", result.error_message)

if __name__ == '__main__':
    unittest.main()
