import base64
import requests
import io
import logging
from typing import Optional
from PIL import Image, ImageEnhance, ImageOps

logger = logging.getLogger(__name__)

class OCRProcessor:
    """
    Handles image validation and download. 
    Note: PaddleOCR has been removed. This class now acts as an image helper.
    """
    
    def __init__(self, max_size_bytes: int = 5 * 1024 * 1024): # 5MB limit
        self.max_size = max_size_bytes
        # No OCR engine init needed

    def optimize_base64(self, b64_string: str) -> str:
        """
        Optimize base64 image: resize to max 1024px and convert to JPEG.
        Returns optimized base64 string.
        """
        try:
             # Basic strip
             if ";base64," in b64_string:
                header, data = b64_string.split(";base64,")
             else:
                header = None
                data = b64_string

             img_data = base64.b64decode(data)
             img = Image.open(io.BytesIO(img_data))
             
             # Resize if too large
             max_dim = 1024
             if max(img.size) > max_dim:
                 img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
             
             # Convert to JPEG for compression (if RGBA, convert to RGB)
             if img.mode in ('RGBA', 'P'):
                 img = img.convert('RGB')
                 
             buffer = io.BytesIO()
             # Quality 85 is good balance
             img.save(buffer, format="JPEG", quality=85)
             
             return base64.b64encode(buffer.getvalue()).decode('utf-8')
        except Exception as e:
            logger.warning(f"Image optimization failed, using original: {e}")
            return b64_string

    def download_image_as_base64(self, url: str) -> Optional[str]:
        """
        Download image from URL and return as base64 string.
        """
        try:
            response = requests.get(url, timeout=10, stream=True)
            response.raise_for_status()
            
            # Size check
            if len(response.content) > self.max_size:
                logger.warning(f"Downloaded image bytes {len(response.content)} exceed limit.")
                return None
            
            # Optimize immediately
            b64 = base64.b64encode(response.content).decode('utf-8')
            return self.optimize_base64(b64)
            
        except Exception as e:
            logger.error(f"Image download failed: {e}")
            return None

    def _preprocess_image(self, img: Image.Image) -> Image.Image:
        """
        Applies preprocessing to improve image quality for Vision model.
        - Grayscale conversion
        - Contrast enhancement
        - Binarization (Thresholding)
        """
        try:
            # 1. Convert to grayscale
            img = img.convert('L')
            
            # 2. Enhance contrast
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(2.0)
            
            # 3. Apply thresholding (binarization)
            # This makes the image pure black and white, removing noise
            img = img.point(lambda x: 0 if x < 128 else 255, '1')
            
            return img
        except Exception as e:
            logger.warning(f"Image preprocessing failed, using original: {e}")
            return img

    def _process_image_data(self, image_bytes: bytes) -> Optional[str]:
        """
        Validate image format. 
        Returns dummy string or None.
        DEPRECATED: Used to do OCR. Now just validates.
        """
        # 1. Size Check
        if len(image_bytes) > self.max_size:
            logger.warning("Image data exceeds size limit.")
            return None

        # 2. Format Validation (using Pillow)
        try:
            img = Image.open(io.BytesIO(image_bytes))
            img.verify() # Verify it's an image
            
            # Re-open for processing (verify closes the file)
            img = Image.open(io.BytesIO(image_bytes))
            
            if img.format.upper() not in ('JPEG', 'JPG', 'PNG', 'BMP', 'WEBP'):
                 logger.warning(f"Unsupported image format: {img.format}")
                 return None
            
            return "VALID_IMAGE" 
                 
        except Exception as e:
             logger.warning(f"Invalid image file: {e}")
             return None

    # Legacy methods stubbed out or removed. 
    # process_base64 and process_url were used for text extraction. 
    # Calling them now should return None to indicate no text extracted.
    
    def process_base64(self, b64_string: str) -> Optional[str]:
         return None

    def process_url(self, url: str) -> Optional[str]:
         return None
