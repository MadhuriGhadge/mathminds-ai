import base64
import enum
import re
import urllib.parse
from dataclasses import dataclass
from typing import Optional, Tuple, Dict, Any
from app.core.ocr import OCRProcessor

class InputType(enum.Enum):
    """Enumeration of supported input types."""
    TEXT = "text"
    LATEX = "latex"
    IMAGE_URL = "image_url"
    BASE64_IMAGE = "base64_image"
    MULTIMODAL = "multimodal"
    UNKNOWN = "unknown"

# ... (omitted dataclass, no changes needed there) ...



@dataclass
class ProcessingResult:
    """Result of the input processing pipeline."""
    input_type: InputType
    cleaned_content: str
    is_valid: bool
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class InputProcessor:
    """
    Handles detection, normalization, and validation of user inputs.
    
    Attributes:
        max_length (int): Maximum allowed characters for text inputs.
    """

    def __init__(self, max_length: int = 5000):
        """
        Initialize the InputProcessor.

        Args:
            max_length: Maximum allowed length for input strings. Defaults to 5000.
        """
        self.max_length = max_length
        # Basic SQL injection and script tag patterns
        self._dangerous_patterns = [
            re.compile(r"<script.*?>.*?</script>", re.IGNORECASE | re.DOTALL),
            re.compile(r"javascript:", re.IGNORECASE),
            re.compile(r"union\s+select", re.IGNORECASE),
            re.compile(r"drop\s+table", re.IGNORECASE),
            re.compile(r"exec\s*\(", re.IGNORECASE),
        ]
        self.ocr_processor = OCRProcessor()

    def process_compound(self, text_input: Optional[str] = None, image_input: Optional[str] = None) -> ProcessingResult:
        """
        Process combined text and image input.
        
        Args:
            text_input: Optional text query.
            image_input: Optional image (Base64 or URL).
            
        Returns:
            ProcessingResult: Combined result.
        """
        cleaned_text = ""
        image_data = None
        detected_type = InputType.UNKNOWN
        error_msg = None
        
        # 1. Process Image if present
        if image_input:
            # Detect if URL or Base64 (naive check)
            if image_input.startswith("http") and "://" in image_input:
                 # URL -> Download
                 image_data = self.ocr_processor.download_image_as_base64(image_input)
                 if not image_data:
                     return ProcessingResult(InputType.IMAGE_URL, "", False, "Failed to download image.")
                 detected_type = InputType.IMAGE_URL # Or promote to MULTIMODAL later
            else:
                 # Assume Base64
                 # Strip prefix if needed
                 if ";base64," in image_input:
                    _, raw_b64 = image_input.split(";base64,")
                 else:
                    raw_b64 = image_input.strip()
                 
                 # Basic validation?
                 if len(raw_b64) < 10:
                      return ProcessingResult(InputType.BASE64_IMAGE, "", False, "Invalid image data.")
                 
                 image_data = raw_b64
                 detected_type = InputType.BASE64_IMAGE

        # 2. Process Text if present
        if text_input:
            cleaned_text = self._normalize_text(text_input)
            
            # If we also have an image, it's MULTIMODAL
            if image_data:
                detected_type = InputType.MULTIMODAL
            elif detected_type == InputType.UNKNOWN:
                # Text only, refined detection (latex vs text)
                detected_type = self._detect_type(cleaned_text)
        
        # 3. Final Validation
        if not cleaned_text and not image_data:
             return ProcessingResult(InputType.UNKNOWN, "", False, "No valid input provided.")
             
        metadata = {}
        if image_data:
            metadata["image_data"] = image_data

        # Validate text content if present (length, safety)
        if cleaned_text:
             is_valid, err = self._validate(cleaned_text, detected_type)
             if not is_valid:
                  return ProcessingResult(detected_type, cleaned_text, False, err)
        
        return ProcessingResult(
            input_type=detected_type,
            cleaned_content=cleaned_text,
            is_valid=True,
            metadata=metadata
        )

    def process(self, input_data: str) -> ProcessingResult:
        """
        Process the raw input string: detect type, normalize, and validate.

        Args:
            input_data: The raw input string from the user.

        Returns:
            ProcessingResult: The processed and validated result.
        """
        if not input_data:
            return ProcessingResult(InputType.UNKNOWN, "", False, "Input cannot be empty.")

        metadata = None
        detected_type = self._detect_type(input_data)
        
        if detected_type in (InputType.TEXT, InputType.LATEX):
            cleaned_content = self._normalize_text(input_data)
        elif detected_type == InputType.BASE64_IMAGE:
             # Process Base64
             # Store raw base64 for Vision Model (strip prefix)
             try:
                if ";base64," in input_data:
                    _, raw_b64 = input_data.split(";base64,")
                else:
                    raw_b64 = input_data
             except ValueError:
                 return ProcessingResult(detected_type, "", False, "Invalid base64 image format.")

             # Skip OCR for Base64 images to avoid "double work" and latency.
             # We rely on Gemini Vision to read the image directly.
             # cleaned_content is set to empty string; hashing will rely on image_data hash.
             extracted_text = "" 
             
             # Attach image data to result
             # Optimize image (resize/compress) to reduce token count and bandwidth
             optimized_b64 = self.ocr_processor.optimize_base64(raw_b64)
             
             metadata = {"image_data": optimized_b64}
             cleaned_content = ""
        elif detected_type == InputType.IMAGE_URL:
             # Process URL: Download and pass as image to Vision (Skip OCR)
             # extracted_text = self.ocr_processor.process_url(input_data)
             
             raw_b64 = self.ocr_processor.download_image_as_base64(input_data)
             
             if not raw_b64:
                 return ProcessingResult(detected_type, "", False, "Failed to download image from URL.")
                 
             # Attach image data (Vision will use this)
             metadata = {"image_data": raw_b64}
             cleaned_content = ""
        else:
            cleaned_content = input_data.strip()
            metadata = None

        is_valid, error_msg = self._validate(cleaned_content, detected_type)

        return ProcessingResult(
            input_type=detected_type,
            cleaned_content=cleaned_content,
            is_valid=is_valid,
            error_message=error_msg,
            metadata=metadata
        )

    def _detect_type(self, data: str) -> InputType:
        """
        Detect the type of the input data.

        Args:
            data: The raw input string.

        Returns:
            InputType: The detected input type.
        """
        data = data.strip()
        
        # Check for Base64 Image
        # A simple heuristic: starts with data:image/ or looks like base64
        if data.startswith("data:image/") and ";base64," in data:
             return InputType.BASE64_IMAGE
        
        # Check for Image URL
        parsed_url = urllib.parse.urlparse(data)
        if parsed_url.scheme in ("http", "https") and any(
            data.lower().endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".gif", ".webp"]
        ):
            return InputType.IMAGE_URL

        # Check for LaTeX
        # Heuristic: contains mathematical delimiters or keywords
        if (
            "$" in data 
            or "\\[" in data 
            or "\\(" in data 
            or re.search(r"\\[a-zA-Z]+", data)
        ):
            return InputType.LATEX

        # Default to text
        return InputType.TEXT

    def _normalize_text(self, text: str) -> str:
        """
        Normalize text input: lowercase, trim, remove extra spaces.

        Args:
            text: The text to normalize.

        Returns:
            str: Normalized text.
        """
        # Lowercase
        text = text.lower()
        
        # Remove extra horizontal whitespace (tabs, multiple spaces)
        text = re.sub(r'[ \t]+', ' ', text)
        
        # Collapse multiple newlines into one
        text = re.sub(r'\n+', '\n', text)
        
        return text.strip()

    def _remove_ocr_artifacts(self, text: str) -> str:
        """Remove common OCR extraction errors."""
        # Remove repeated characters (OCR artifact)
        text = re.sub(r'([!?.\-_=])\1{3,}', r'\1\1', text)
        
        # Remove random special chars at start/end
        # Added '-' to the allowed list to prevent stripping negative numbers
        text = re.sub(r'^[^a-zA-Z0-9\(\[\{$\-]*', '', text)
        text = re.sub(r'[^a-zA-Z0-9\)\]\}\$]*$', '', text)
        
        return text

    def _validate(self, content: str, input_type: InputType) -> Tuple[bool, Optional[str]]:
        """
        Validate the content based on its type and generic safety rules.

        Args:
            content: The content to validate.
            input_type: The type of the content.

        Returns:
            Tuple[bool, Optional[str]]: (IsValid, ErrorMessage)
        """
        if len(content) > self.max_length and input_type != InputType.BASE64_IMAGE:
            return False, f"Input length exceeds maximum limit of {self.max_length} characters."
        
        # For Base64, we allow larger size, but maybe still impose a limit? 
        # For now, let's assume max_length applies to text/latex/url
        if input_type == InputType.BASE64_IMAGE:
             # Heuristic check for base64 validity
             if len(content) > 5_000_000: #5MB limit catch
                 return False, "Image data too large."
             # Further base64 validation could be done here if needed
             return True, None

        if input_type == InputType.IMAGE_URL:
             # Basic URL validation done in detect and OCR, but check again for safety
             parsed = urllib.parse.urlparse(content)
             # Note: For IMAGE_URL, 'content' here is technically the ACTUALLY EXTRACTED TEXT now if we look at flow above?
             # Wait, logic check: 
             # In `process`:
             # 1. detect_type -> IMAGE_URL
             # 2. if IMAGE_URL -> ocr -> extracted_text
             # 3. cleaned_content = extracted_text
             # 4. _validate(cleaned_content, IMAGE_URL)
             # So content passed to validate is TEXT.
             # BUT `detect_type` is IMAGE_URL.
             # So `_validate` logic for IMAGE_URL checking scheme is invalid b/c content is now text.
             # We should rely on OCR processor to have validated the image/url itself.
             # So here for IMAGE_URL/BASE64_IMAGE, we are validating the EXTRACTED text.
             pass 
             
             # if parsed.scheme not in ('http', 'https'):
             #     return False, "Invalid URL scheme."
             # return True, None

        # Check for dangerous payloads in text/latex
        for pattern in self._dangerous_patterns:
            if pattern.search(content):
                return False, "Input contains potentially dangerous content."

        return True, None
