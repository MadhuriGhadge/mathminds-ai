"""
deps.py — Dependency injection for FastAPI.

Fixes applied vs. original:
  1. `get_cache_manager` and `get_db_manager` used `@lru_cache()` but their
     factory functions call `get_redis_pool()` / `get_mongo_client()` which are
     themselves guarded by module-level globals. `lru_cache` on these is
     harmless but redundant — kept for explicit singleton semantics, added a
     comment explaining why.
  2. `get_redis_client()` returned a new `redis.Redis` object on every call
     (sharing the pool, so connections were fine). Made the intent explicit with
     a docstring.
  3. Added `close()` helpers so lifespan shutdown can cleanly release
     connections if needed in the future.
"""

import logging
from functools import lru_cache
from threading import Lock
from typing import Optional

import pymongo
import redis

from app.core.orchestrator import Orchestrator
from app.core.settings import settings
from app.memory.cache import CacheManager
from app.memory.database import DatabaseManager
from app.memory.semantic_cache import SemanticCache

logger = logging.getLogger(__name__)

# ── Module-level singletons ───────────────────────────────────────────────────
_redis_pool:   Optional[redis.ConnectionPool] = None

_mongo_client: Optional[pymongo.MongoClient]  = None


def get_redis_pool() -> redis.ConnectionPool:
    """Return (or lazily create) the shared Redis connection pool."""
    global _redis_pool
    if _redis_pool:
        return _redis_pool
    redis_url = settings.REDIS_URL
    if not redis_url:
        raise ValueError("REDIS_URL is not configured.")
    try:
        _redis_pool = redis.ConnectionPool.from_url(redis_url, decode_responses=True)
        logger.info(f"Initialized Redis pool: {redis_url}")
        return _redis_pool
    except Exception as e:
        logger.error(f"Failed to create Redis pool: {e}")
        raise


def get_redis_client() -> redis.Redis:
    """
    Return a Redis client that borrows a connection from the shared pool.
    Each call returns a lightweight client wrapper — no new connection is
    opened unless the pool needs to grow.
    """
    return redis.Redis(connection_pool=get_redis_pool())


def get_mongo_client() -> pymongo.MongoClient:
    """Return (or lazily create) the shared MongoDB client."""
    global _mongo_client
    if _mongo_client:
        return _mongo_client
    try:
        _mongo_client = pymongo.MongoClient(
            settings.MONGO_URI,
            serverSelectionTimeoutMS=5000,
            minPoolSize=1,
            maxPoolSize=50,
        )
        logger.info("Initialized MongoDB client.")
        return _mongo_client
    except Exception as e:
        logger.error(f"Failed to create MongoDB client: {e}")
        raise


# lru_cache gives singleton semantics: the first call creates the manager and
# all subsequent calls return the same instance.
@lru_cache()
def get_cache_manager() -> CacheManager:
    return CacheManager(connection_pool=get_redis_pool())


@lru_cache()
def get_db_manager() -> DatabaseManager:
    return DatabaseManager(client=get_mongo_client())


@lru_cache()
def get_semantic_cache() -> SemanticCache:
    return SemanticCache(
        redis_client=get_redis_client(),
        gemini_api_key=settings.GOOGLE_API_KEY
    )


# ── Orchestrator singleton (thread-safe double-checked locking) ───────────────
_orchestrator:      Optional[Orchestrator] = None
_orchestrator_lock: Lock                   = Lock()


def get_orchestrator() -> Orchestrator:
    """
    Thread-safe singleton Orchestrator.
    Injects the shared Redis client so the ADK agent can use it for quota
    tracking without opening a second connection pool.
    """
    global _orchestrator
    if _orchestrator:
        return _orchestrator

    with _orchestrator_lock:
        # Second check inside the lock — another thread may have initialized
        # while we were waiting.
        if _orchestrator:
            return _orchestrator

        logger.info("Initializing Orchestrator singleton…")

        redis_client: Optional[redis.Redis] = None
        try:
            redis_client = get_redis_client()
        except Exception:
            logger.warning("Redis unavailable — quota guard will be skipped.")

        _orchestrator = Orchestrator(
            cache_manager=get_cache_manager(),
            db_manager=get_db_manager(),
            semantic_cache=get_semantic_cache(),
            redis_client=redis_client,
        )
        return _orchestrator


# ── Optional teardown helpers (call from lifespan shutdown if needed) ─────────

def close_redis():
    global _redis_pool
    if _redis_pool:
        try:
            _redis_pool.disconnect()
            logger.info("Redis pool disconnected.")
        except Exception as e:
            logger.warning(f"Redis pool disconnect error: {e}")
        _redis_pool = None


def close_mongo():
    global _mongo_client
    if _mongo_client:
        try:
            _mongo_client.close()
            logger.info("MongoDB client closed.")
        except Exception as e:
            logger.warning(f"MongoDB close error: {e}")
        _mongo_client = None