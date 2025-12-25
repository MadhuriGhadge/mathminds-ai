from pathlib import Path

def load_image_bytes(image_path: str) -> bytes:
    return Path(image_path).read_bytes()
