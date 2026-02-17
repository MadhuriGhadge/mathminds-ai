
import base64
import requests
import io
import logging
import numpy as np
from typing import Optional, List
from PIL import Image, ImageEnhance, UnidentifiedImageError
import binascii
try:
    from paddleocr import PaddleOCR
except ImportError:
    PaddleOCR = None

logger = logging.getLogger(__name__)

class OCRProcessor:
    """
    Handles OCR text extraction using PaddleOCR and image preprocessing.
    """
    
    _os_instance = None # Singleton for OCR engine

    def __init__(self, max_size_bytes: int = 5 * 1024 * 1024): # 5MB limit
        self.max_size = max_size_bytes
        self.ocr_engine = None

    @property
    def engine(self):
        """Lazy load PaddleOCR engine."""
        if self.ocr_engine is None:
            if PaddleOCR:
                logger.info("Initializing PaddleOCR engine...")
                # deterministic=True ensures consistent results
                self.ocr_engine = PaddleOCR(use_angle_cls=True, lang='en')
            else:
                logger.error("PaddleOCR not installed.")
                return None
        return self.ocr_engine

    def extract_text(self, headers_b64: Optional[str] = None, image_data: Optional[str] = None) -> str:
        """
        Extract text from base64 image data.
        Arg 'headers_b64' is for backward compat/legacy signature matching if any, 
        but we expect 'image_data' (base64 string).
        
        Args:
            image_data: Base64 string of the image.
            
        Returns:
            Extracted text string or empty string on failure.
        """
        # Handle positional args if someone calls extract_text(b64)
        target_b64 = image_data or headers_b64 
        if not target_b64:
            return ""

        if not self.engine:
            return "OCR Engine Unavailable"

        try:
            # 1. Decode Base64 to Array
            if ";base64," in target_b64:
                _, target_b64 = target_b64.split(";base64,")
            
            try:
                img_bytes = base64.b64decode(target_b64)
                img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
                img_arr = np.array(img)
            except (binascii.Error, UnidentifiedImageError, ValueError) as e:
                 logger.error(f"Image decoding failed: {e}")
                 return f"Error: Invalid image data ({str(e)})"

            # 2. Run OCR
            result = self.engine.ocr(img_arr, cls=True)
            
            # 3. Parse Results
            extracted_lines = []
            if result and result[0]:
                for line in result[0]:
                    text = line[1][0]
                    confidence = line[1][1]
                    if confidence > 0.5: # Confidence threshold
                        extracted_lines.append(text)
            
            full_text = "\n".join(extracted_lines)
            logger.info(f"OCR extracted {len(full_text)} chars.")
            return full_text

        except Exception as e:
            logger.error(f"OCR Failed: {e}")
            return f"Error reading image: {e}"

    def optimize_base64(self, b64_string: str) -> str:
        """
        Optimize base64 image: resize to max 1024px and convert to JPEG.
        Returns optimized base64 string.
        """
        try:
             if ";base64," in b64_string:
                _, data = b64_string.split(";base64,")
             else:
                data = b64_string

             img_data = base64.b64decode(data)
             img = Image.open(io.BytesIO(img_data))
             
             max_dim = 1024
             if max(img.size) > max_dim:
                 img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
             
             if img.mode in ('RGBA', 'P'):
                 img = img.convert('RGB')
                 
             buffer = io.BytesIO()
             img.save(buffer, format="JPEG", quality=85)
             return base64.b64encode(buffer.getvalue()).decode('utf-8')
        except Exception as e:
            logger.warning(f"Image optimization failed: {e}")
            return b64_string

    def download_image_as_base64(self, url: str) -> Optional[str]:
        """Download image from URL and return as base64 string."""
        try:
            response = requests.get(url, timeout=10, stream=True)
            response.raise_for_status()
            if len(response.content) > self.max_size:
                return None
            b64 = base64.b64encode(response.content).decode('utf-8')
            return self.optimize_base64(b64)
        except Exception as e:
            logger.error(f"Image download failed: {e}")
            return None
