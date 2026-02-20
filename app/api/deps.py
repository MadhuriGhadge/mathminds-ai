"""
deps.py — Dependency injection for FastAPI.
Key change: get_orchestrator() now passes the shared Redis client into Orchestrator
so the ADK agent can use it for quota tracking without creating a second connection.
"""

import os
import redis
import pymongo
from functools import lru_cache
from typing import Optional
import logging

from app.core.orchestrator import Orchestrator
from app.memory.cache import CacheManager
from app.memory.database import DatabaseManager
from app.core.settings import settings

logger = logging.getLogger(__name__)

# ── Singletons ────────────────────────────────────────────────────────────────
_redis_pool: Optional[redis.ConnectionPool] = None
_mongo_client: Optional[pymongo.MongoClient] = None


def get_redis_pool() -> redis.ConnectionPool:
    global _redis_pool
    if _redis_pool:
        return _redis_pool
    try:
        redis_url = settings.REDIS_URL
        if not redis_url:
            raise ValueError("REDIS_URL is not set.")
        _redis_pool = redis.ConnectionPool.from_url(redis_url, decode_responses=True)
        logger.info(f"Initialized Redis Pool: {redis_url}")
        return _redis_pool
    except Exception as e:
        logger.error(f"Failed to create Redis pool: {e}")
        raise


def get_redis_client() -> redis.Redis:
    """Return a Redis client using the shared pool."""
    return redis.Redis(connection_pool=get_redis_pool())


def get_mongo_client() -> pymongo.MongoClient:
    global _mongo_client
    if _mongo_client:
        return _mongo_client
    try:
        _mongo_client = pymongo.MongoClient(
            settings.MONGO_URI,
            serverSelectionTimeoutMS=5000,
            minPoolSize=1,
            maxPoolSize=50
        )
        logger.info("Initialized MongoDB Client")
        return _mongo_client
    except Exception as e:
        logger.error(f"Failed to create Mongo client: {e}")
        raise


@lru_cache()
def get_cache_manager() -> CacheManager:
    return CacheManager(connection_pool=get_redis_pool())


@lru_cache()
def get_db_manager() -> DatabaseManager:
    return DatabaseManager(client=get_mongo_client())


from threading import Lock

_orchestrator: Optional[Orchestrator] = None
_orchestrator_lock = Lock()


def get_orchestrator() -> Orchestrator:
    """Thread-safe singleton Orchestrator, with Redis client injected."""
    global _orchestrator
    if _orchestrator:
        return _orchestrator

    with _orchestrator_lock:
        if _orchestrator:
            return _orchestrator

        logger.info("Initializing Orchestrator Singleton...")

        # Pass the shared Redis client so the agent can use it for quota checks
        # without opening a separate connection pool.
        try:
            redis_client = get_redis_client()
        except Exception:
            redis_client = None
            logger.warning("Redis unavailable — quota guard will be skipped.")

        _orchestrator = Orchestrator(
            cache_manager=get_cache_manager(),
            db_manager=get_db_manager(),
            redis_client=redis_client,   # ← new param passed to Orchestrator
        )
        return _orchestrator