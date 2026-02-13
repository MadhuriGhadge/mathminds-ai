import logging
import torch
from transformers import TrOCRProcessor, VisionEncoderDecoderModel
from PIL import Image
import io

logger = logging.getLogger(__name__)

class AdvancedOCR:
    """
    Advanced OCR using Hugging Face Transformers (TrOCR).
    Specialized for handwritten text and mathematical expressions.
    """

    def __init__(self, model_name: str = "microsoft/trocr-base-handwritten"):
        """
        Initialize the TrOCR model and processor.
        """
        self.model_name = model_name
        self.processor = None
        self.model = None
        
        # Lazy loading to avoid heavy startup time if not needed immediately
        self._loaded = False

    def load_model(self):
        """
        Load the model into memory.
        """
        if self._loaded:
            return

        try:
            logger.info(f"Loading TrOCR model: {self.model_name}...")
            self.processor = TrOCRProcessor.from_pretrained(self.model_name)
            self.model = VisionEncoderDecoderModel.from_pretrained(self.model_name)
            
            # Move to GPU if available
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            self.model.to(self.device)
            
            self._loaded = True
            logger.info("TrOCR model loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load TrOCR model: {e}")
            self._loaded = False
            raise e

    def extract_handwriting(self, image: Image.Image) -> str:
        """
        Extract handwritten text from a PIL Image.
        """
        if not self._loaded:
            self.load_model()
        
        try:
            # Prepare image
            if image.mode != "RGB":
                image = image.convert("RGB")
                
            pixel_values = self.processor(images=image, return_tensors="pt").pixel_values
            pixel_values = pixel_values.to(self.device)

            # Generate text
            generated_ids = self.model.generate(pixel_values)
            generated_text = self.processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
            
            return generated_text
            
        except Exception as e:
            logger.error(f"TrOCR extraction failed: {e}")
            return ""

    def process_image_bytes(self, image_bytes: bytes) -> str:
        """
        Process raw image bytes.
        """
        try:
            image = Image.open(io.BytesIO(image_bytes))
            return self.extract_handwriting(image)
        except Exception as e:
            logger.error(f"Error processing image bytes: {e}")
            return ""
