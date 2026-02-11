import hashlib
import unicodedata

def generate_problem_hash(text: str, image_data: str = None) -> str:
    """
    Generates a deterministic SHA256 hash for a given problem text AND optional image.
    """
    if not text and not image_data:
        raise ValueError("Input text and image cannot both be empty for hashing.")

    # Normalize unicode characters
    normalized_text = unicodedata.normalize('NFKC', text or "")
    
    # Lowercase and strip whitespace
    cleaned_text = normalized_text.lower().strip()
    
    # Base content
    content_to_hash = cleaned_text
    
    # Append image data if present
    if image_data:
        # Image data is usually a long base64 string. 
        # We append it to ensure uniqueness for visual problems.
        content_to_hash += f"|image:{image_data}"

    # Encode to bytes
    encoded_text = content_to_hash.encode('utf-8')
    
    # Generate SHA256 hash
    return hashlib.sha256(encoded_text).hexdigest()
