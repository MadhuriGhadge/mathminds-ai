import os
import json
import logging
from typing import Optional, Any, Union
import redis
from redis.exceptions import RedisError

# Configure logging
logger = logging.getLogger(__name__)

class RedisCache:
    def __init__(self, redis_url: Optional[str] = None):
        """
        Initialize the RedisCache wrapper.
        
        Args:
            redis_url: Connection URL for Redis. Defaults to REDIS_URL env var or localhost.
        """
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.client = None
        self._connect()

    def _connect(self):
        """Establish Redis connection."""
        try:
            self.client = redis.from_url(self.redis_url, decode_responses=True)
            self.client.ping()
            logger.info("Connected to Redis cache.")
        except RedisError as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.client = None

    def get(self, problem_hash: str) -> Optional[Any]:
        """
        Retrieve result from cache using problem_hash.
        
        Args:
            problem_hash: The unique hash of the problem.
            
        Returns:
            The cached result (deserialized) or None if not found/error.
        """
        if not self.client:
            return None
            
        try:
            data = self.client.get(problem_hash)
            if data:
                return json.loads(data)
            return None
        except (RedisError, json.JSONDecodeError) as e:
            logger.error(f"Error retrieving from cache: {e}")
            return None

    def set(self, problem_hash: str, result: Any, ttl: int = 86400) -> bool:
        """
        Store result in cache with TTL.
        
        Args:
            problem_hash: The unique hash key.
            result: The data to cache (will be JSON serialized).
            ttl: Time-to-live in seconds (default 1 day).
            
        Returns:
            True if successful, False otherwise.
        """
        if not self.client:
            return False
            
        try:
            serialized = json.dumps(result)
            return bool(self.client.setex(problem_hash, ttl, serialized))
        except (RedisError, TypeError) as e:
            logger.error(f"Error setting cache: {e}")
            return False
