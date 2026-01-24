import json
import logging
import os
from typing import Any, Dict, Optional

import redis
from redis.exceptions import RedisError

# Configure logging
logger = logging.getLogger(__name__)

class CacheManager:
    """
    Manages Redis cache operations for the AI system.
    Handles connections, serialization, and failure scenarios gracefully.
    """

    def __init__(self, redis_url: Optional[str] = None, connection_pool: Optional[redis.ConnectionPool] = None):
        """
        Initialize the CacheManager.

        Args:
            redis_url: Redis connection string (used if pool not provided).
            connection_pool: Existing Redis connection pool.
        """
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.redis_client = None
        
        try:
            if connection_pool:
                self.redis_client = redis.Redis(connection_pool=connection_pool, decode_responses=True)
            else:
                # If no pool provided, create standard client (which uses internal pool)
                # But typically we want to pass the pool.
                self.redis_client = redis.from_url(self.redis_url, decode_responses=True)
            
            # Fast ping to verify connection
            self.redis_client.ping()
            logger.info(f"Successfully connected to Redis at {self.redis_url}")
        
        except RedisError as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.redis_client = None

    # _connect method is removed/merged into __init__ since we prefer injection

    def get_cached_answer(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a cached answer by its hash key.

        Args:
            cache_key: The unique hash key for the problem.

        Returns:
            Optional[Dict[str, Any]]: The cached answer info if found and valid, else None.
        """
        if not self.redis_client:
            logger.warning("Redis client is not available. Skipping cache lookup.")
            return None

        try:
            data = self.redis_client.get(cache_key)
            if data:
                logger.info(f"Cache hit for key: {cache_key}")
                return json.loads(data)
            logger.info(f"Cache miss for key: {cache_key}")
            return None
        except RedisError as e:
            logger.error(f"Redis error during get operations: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode cached data for key {cache_key}: {e}")
            return None

    def set_cached_answer(self, cache_key: str, answer: Dict[str, Any], ttl: int = 86400) -> bool:
        """
        Cache an answer with a TTL.

        Args:
            cache_key: The unique hash key.
            answer: The answer data to cache (will be JSON serialized).
            ttl: Time-to-live in seconds. Defaults to 86400 (24 hours).

        Returns:
            bool: True if successful, False otherwise.
        """
        if not self.redis_client:
            logger.warning("Redis client is not available. Skipping cache write.")
            return False

        try:
            serialized_data = json.dumps(answer)
            self.redis_client.setex(cache_key, ttl, serialized_data)
            logger.info(f"Successfully cached answer for key: {cache_key} with TTL {ttl}")
            return True
        except (RedisError, TypeError) as e:
            # TypeError catches JSON serialization errors
            logger.error(f"Failed to cache answer for key {cache_key}: {e}")
            return False

    def set_if_not_exists(self, cache_key: str, answer: Dict[str, Any], ttl: int = 86400) -> bool:
        """
        Set cache only if key doesn't exist (atomic operation).
        Prevents thundering herd when multiple requests populate cache.
        
        Args:
            cache_key: The unique hash key.
            answer: The answer data to cache.
            ttl: Time-to-live in seconds.

        Returns:
            bool: True if set, False if key already existed or error.
        """
        if not self.redis_client:
            return False
        
        try:
            serialized_data = json.dumps(answer)
            # SETNX is atomic - only succeeds if key doesn't exist
            # Redis-py set() with nx=True is equivalent to SETNX + EXPIRE
            result = self.redis_client.set(
                cache_key, 
                serialized_data, 
                ex=ttl, 
                nx=True  # Only set if not exists
            )
            return bool(result)
        except Exception as e:
            logger.error(f"Failed to set_if_not_exists for {cache_key}: {e}")
            return False
