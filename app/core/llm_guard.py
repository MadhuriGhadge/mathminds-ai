"""
llm_guard.py — Redis-backed daily rate limiter for LLM calls.

Replaces the asyncio.Semaphore(1) approach, which only limited concurrency
(not total daily calls) and did not survive server restarts.

Strategy:
  - Each user gets a daily counter key in Redis: llm_quota:<user_id>:<YYYY-MM-DD>
  - TTL is set to 25 hours so the key auto-expires safely past midnight.
  - Global fallback key used when user_id is unknown.
  - Quota: MAX_LLM_CALLS_PER_DAY (default 18, leaving 2 RPD buffer from the 20 RPD limit).
  - check_and_increment() is atomic via Redis INCR — safe under concurrent requests.
"""

import logging
import os
from datetime import datetime, timezone
from app.core.settings import settings

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
# MAX_LLM_CALLS_PER_DAY is now in settings.MAX_LLM_CALLS_PER_DAY
QUOTA_TTL_SECONDS: int = 25 * 3600  # 25 hours — expires safely after midnight
GLOBAL_FALLBACK_USER = "global"
# ─────────────────────────────────────────────────────────────────────────────


def _quota_key(user_id: str) -> str:
    """Build a per-user, per-day Redis key."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return f"llm_quota:{user_id}:{today}"


def check_and_increment(redis_client, user_id: str | None = None) -> tuple[bool, int, int]:
    """
    Atomically check if the user is within quota and increment their counter.

    Args:
        redis_client: A connected redis.Redis instance (sync).
        user_id:      Firebase UID or None for anonymous/global fallback.

    Returns:
        (allowed, current_count, limit)
        - allowed:       True if the call is permitted.
        - current_count: Counter value AFTER this increment (or before if denied).
        - limit:         The daily cap.
    """
    uid = user_id or GLOBAL_FALLBACK_USER
    key = _quota_key(uid)

    try:
        # INCR is atomic. If key doesn't exist Redis creates it at 0 then increments.
        new_count: int = redis_client.incr(key)

        # Set TTL only on first use (when count == 1), avoids resetting it on each call.
        if new_count == 1:
            redis_client.expire(key, QUOTA_TTL_SECONDS)

        if new_count > settings.MAX_LLM_CALLS_PER_DAY:
            # Rollback: decrement so we don't waste the quota slot.
            redis_client.decr(key)
            logger.warning(
                f"LLM quota exceeded for user={uid} | count={new_count - 1}/{settings.MAX_LLM_CALLS_PER_DAY}"
            )
            return False, new_count - 1, settings.MAX_LLM_CALLS_PER_DAY

        logger.info(
            f"LLM quota used: user={uid} | {new_count}/{settings.MAX_LLM_CALLS_PER_DAY}"
        )
        return True, new_count, settings.MAX_LLM_CALLS_PER_DAY

    except Exception as e:
        # Redis unavailable → fail open (allow the call) so the app doesn't break.
        # Log loudly so you know the guard is down.
        logger.error(f"LLM quota Redis error (failing open): {e}")
        return True, -1, settings.MAX_LLM_CALLS_PER_DAY


def get_remaining(redis_client, user_id: str | None = None) -> int:
    """
    Return how many LLM calls the user has left today.
    Returns MAX_LLM_CALLS_PER_DAY if Redis is unavailable.
    """
    uid = user_id or GLOBAL_FALLBACK_USER
    key = _quota_key(uid)
    try:
        raw = redis_client.get(key)
        used = int(raw) if raw else 0
        return max(0, settings.MAX_LLM_CALLS_PER_DAY - used)
    except Exception as e:
        logger.error(f"LLM quota get_remaining Redis error: {e}")
        return settings.MAX_LLM_CALLS_PER_DAY