import hashlib
import unicodedata

def generate_problem_hash(text: str) -> str:
    """
    Generates a deterministic SHA256 hash for a given problem text.
    
    The text is normalized (NFKC), lowercased, and stripped of leading/trailing
    whitespace ensuring that semantically identical inputs (ignoring minor
    formatting differences) produce the same hash.

    Args:
        text (str): The input problem text to hash.

    Returns:
        str: The hexadecimal SHA256 hash string.
    """
    if not text:
        raise ValueError("Input text cannot be empty/None for hashing.")

    # Normalize unicode characters to NFKC form (compatibility decomposition)
    # This helps in treating different representations of same characters as identical.
    normalized_text = unicodedata.normalize('NFKC', text)
    
    # Lowercase and strip whitespace
    cleaned_text = normalized_text.lower().strip()
    
    # Encode to bytes
    encoded_text = cleaned_text.encode('utf-8')
    
    # Generate SHA256 hash
    return hashlib.sha256(encoded_text).hexdigest()
