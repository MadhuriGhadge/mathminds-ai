import unittest
import sys
import os

# Ensure app is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.input_processor import InputProcessor, InputType

class TestInputProcessor(unittest.TestCase):
    def setUp(self):
        self.processor = InputProcessor()

    def test_text_normalization(self):
        """Test basic text normalization."""
        raw_input = "  HELLO   World  "
        result = self.processor.process(raw_input)
        self.assertTrue(result.is_valid)
        self.assertEqual(result.input_type, InputType.TEXT)
        self.assertEqual(result.cleaned_content, "hello world")

    def test_latex_detection(self):
        """Test detection of LaTeX content."""
        latex_input = "Solve $x^2 + 2x + 1 = 0$"
        result = self.processor.process(latex_input)
        self.assertTrue(result.is_valid)
        self.assertEqual(result.input_type, InputType.LATEX)
        # Normalization should still prevent dangerous stuff but allow latex chars
        self.assertIn("solve $x^2 + 2x + 1 = 0$", result.cleaned_content)

    def test_image_url_detection(self):
        """Test detection of image URLs."""
        url_input = "https://example.com/equation.png"
        result = self.processor.process(url_input)
        self.assertTrue(result.is_valid)
        self.assertEqual(result.input_type, InputType.IMAGE_URL)
        self.assertEqual(result.cleaned_content, url_input)

    def test_base64_detection(self):
        """Test detection of base64 images."""
        base64_input = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
        result = self.processor.process(base64_input)
        self.assertTrue(result.is_valid)
        self.assertEqual(result.input_type, InputType.BASE64_IMAGE)

    def test_dangerous_content(self):
        """Test rejection of dangerous content."""
        dangerous_inputs = [
            "<script>alert(1)</script>",
            "javascript:alert(1)",
            "DROP TABLE users",
            "UNION SELECT * FROM passwords"
        ]
        for inp in dangerous_inputs:
            result = self.processor.process(inp)
            self.assertFalse(result.is_valid, f"Should reject: {inp}")
            self.assertIn("potentially dangerous", result.error_message)

    def test_empty_input(self):
        """Test empty input handling."""
        result = self.processor.process("")
        self.assertFalse(result.is_valid)
        self.assertEqual(result.input_type, InputType.UNKNOWN)

    def test_max_length(self):
        """Test max length enforcement."""
        long_input = "a" * 5001
        result = self.processor.process(long_input)
        self.assertFalse(result.is_valid)
        self.assertIn("length exceeds", result.error_message)

if __name__ == '__main__':
    unittest.main()
