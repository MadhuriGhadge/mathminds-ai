import json
import logging
from typing import Any, Dict, Optional

import redis
from redis.exceptions import RedisError

from app.core.settings import settings

logger = logging.getLogger(__name__)


class CacheManager:

    CACHE_PREFIX = "mathminds:cache:"
    MAX_CACHE_SIZE = 50000

    def __init__(
        self,
        redis_url: Optional[str] = None,
        connection_pool: Optional[redis.ConnectionPool] = None,
    ):

        self.redis_url = redis_url or settings.REDIS_URL
        self.redis_client = None

        try:

            if connection_pool:
                self.redis_client = redis.Redis(
                    connection_pool=connection_pool,
                    decode_responses=True,
                )
            else:
                self.redis_client = redis.from_url(
                    self.redis_url,
                    decode_responses=True,
                    socket_timeout=2,
                    socket_connect_timeout=2,
                )

            self.redis_client.ping()

            logger.info(f"Connected to Redis at {self.redis_url}")

        except RedisError as e:

            logger.error(f"Redis connection failed: {e}")
            self.redis_client = None

    def _serialize(self, data: Any) -> str:
        return json.dumps(data, default=str)

    def _prefixed(self, key: str) -> str:
        return f"{self.CACHE_PREFIX}{key}"

    def get_cached_answer(self, cache_key: str) -> Optional[Dict[str, Any]]:

        if not self.redis_client:
            return None

        try:

            key = self._prefixed(cache_key)

            data = self.redis_client.get(key)

            if data:
                logger.debug(f"Cache hit: {key}")
                return json.loads(data)

            return None

        except (RedisError, json.JSONDecodeError) as e:

            logger.error(f"Cache read error: {e}")
            return None

    def set_cached_answer(
        self,
        cache_key: str,
        answer: Dict[str, Any],
        ttl: int = 86400,
    ) -> bool:

        if not self.redis_client:
            return False

        try:

            key = self._prefixed(cache_key)

            serialized_data = self._serialize(answer)

            if len(serialized_data) > self.MAX_CACHE_SIZE:
                logger.warning("Cache skipped: payload too large")
                return False

            self.redis_client.setex(key, ttl, serialized_data)

            return True

        except (RedisError, TypeError) as e:

            logger.error(f"Cache write failed: {e}")
            return False

    def set_if_not_exists(
        self,
        cache_key: str,
        answer: Dict[str, Any],
        ttl: int = 86400,
    ) -> bool:

        if not self.redis_client:
            return False

        try:

            key = self._prefixed(cache_key)

            serialized_data = self._serialize(answer)

            result = self.redis_client.set(
                key,
                serialized_data,
                ex=ttl,
                nx=True,
            )

            return bool(result)

        except Exception as e:

            logger.error(f"set_if_not_exists failed: {e}")
            return False

    def delete(self, cache_key: str) -> bool:

        if not self.redis_client:
            return False

        try:

            key = self._prefixed(cache_key)

            return bool(self.redis_client.delete(key))

        except RedisError:

            return False

    def stats(self) -> Dict[str, Any]:

        if not self.redis_client:
            return {}

        try:

            info = self.redis_client.info()

            return {
                "used_memory": info.get("used_memory_human"),
                "connected_clients": info.get("connected_clients"),
                "keyspace_hits": info.get("keyspace_hits"),
                "keyspace_misses": info.get("keyspace_misses"),
            }

        except Exception:

            return {}