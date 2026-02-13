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

# --- Connection Pools (Global Singletons) ---
# We use global variables instead of lru_cache for connections so we can reset them if needed
_redis_pool: Optional[redis.ConnectionPool] = None
_mongo_client: Optional[pymongo.MongoClient] = None

def get_redis_pool() -> redis.ConnectionPool:
    """
    Creates a shared Redis connection pool.
    Not cached with lru_cache to avoid caching failed states or stale configs forever.
    Uses a global singleton pattern with lazy validation.
    """
    global _redis_pool
    if _redis_pool:
        return _redis_pool

    try:
        redis_url = settings.REDIS_URL
        if not redis_url:
            raise ValueError("REDIS_URL is not set.")

        pool = redis.ConnectionPool.from_url(redis_url, decode_responses=True)
        
        # Optional: Fail fast check
        # r = redis.Redis(connection_pool=pool)
        # r.ping()
        
        _redis_pool = pool
        logger.info(f"Initialized Redis Pool: {redis_url}")
        return _redis_pool
    except Exception as e:
        logger.error(f"Failed to create Redis connection pool: {e}")
        raise

def get_mongo_client() -> pymongo.MongoClient:
    """
    Creates a shared MongoDB client.
    """
    global _mongo_client
    if _mongo_client:
        return _mongo_client

    try:
        mongo_uri = settings.MONGO_URI
        client = pymongo.MongoClient(
            mongo_uri, 
            serverSelectionTimeoutMS=5000,
            minPoolSize=1,
            maxPoolSize=50
        )
        _mongo_client = client
        logger.info("Initialized MongoDB Client")
        return _mongo_client
    except Exception as e:
        logger.error(f"Failed to create Mongo client: {e}")
        raise

# --- Component Factories ---

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
    """
    Thread-safe Singleton provider for Orchestrator.
    Ensures heavy models are loaded exactly once per process.
    """
    global _orchestrator
    if _orchestrator:
        return _orchestrator

    with _orchestrator_lock:
        # Double-check locking
        if _orchestrator:
            return _orchestrator
            
        logger.info("Initializing Orchestrator Singleton...")
        _orchestrator = Orchestrator(
            cache_manager=get_cache_manager(),
            db_manager=get_db_manager()
        )
        return _orchestrator
