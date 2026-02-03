import logging
import sys
from pythonjsonlogger import jsonlogger

def configure_logging():
    """
    Configures the root logger to output logs in JSON format.
    """
    logger = logging.getLogger()
    
    # Remove existing handlers to avoid duplication/conflict with Uvicorn default
    if logger.handlers:
        for handler in logger.handlers:
            logger.removeHandler(handler)
    
    handler = logging.StreamHandler(sys.stdout)
    
    # Custom format
    formatter = jsonlogger.JsonFormatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z"
    )
    
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    
    # Also silence some noisy libraries if needed
    logging.getLogger("uvicorn.access").disabled = True # We might replace this with our own access log if desired
