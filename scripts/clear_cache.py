
import asyncio
import sys
import os
import logging
from dotenv import load_dotenv

# Load env vars
load_dotenv(override=True)

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.memory.cache import CacheManager

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("cache_cleaner")

def clear_cache():
    print("Cleaning Redis Cache...")
    try:
        cache = CacheManager()
        if cache.redis_client:
            cache.redis_client.flushall()
            print("Cache Flushed Successfully!")
        else:
            print("Redis not connected.")
    except Exception as e:
        print(f"Error clearing cache: {e}")

if __name__ == "__main__":
    clear_cache()
