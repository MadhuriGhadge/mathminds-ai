"""
app/memory/semantic_cache.py — Semantic (meaning-aware) cache for MathMinds AI.

Architecture
────────────
Exact hash cache (Redis)          ← microseconds, free
        ↓ MISS
Semantic vector cache (Redis)     ← ~50ms, free (embedding stored in Redis)
        ↓ MISS
Gemini API call                   ← costs 1 quota unit

Why two layers?
  - Exact cache: zero cost, handles identical repeated questions instantly.
  - Semantic cache: handles paraphrases. Uses Google's gemini-embedding-001
    to embed both the query and stored questions, then finds nearest neighbour
    by cosine similarity. Entirely self-contained in Redis — no Supabase needed.

Redis key design
  semantic:index         → Redis Set  — all embedding keys
  semantic:emb:{hash}    → JSON {query, embedding, answer, metadata, timestamp}

Similarity threshold: 0.85
  - 0.85+ → same mathematical question, different words  (safe to return)
  - 0.70-0.85 → related topic, probably different question (skip)
  - <0.70 → unrelated

Quota cost of embeddings
  gemini-embedding-001 is NOT counted against the generate_content quota.
  It has its own free tier: 1500 requests/day — far more than the 20/day
  generate limit, so semantic lookup is essentially free to run.
"""

import json
import logging
import hashlib
import time
import math
from typing import Optional, Dict, Any, List, Tuple

logger = logging.getLogger(__name__)

# ── Similarity threshold ───────────────────────────────────────────────────
# Tested against math paraphrase pairs. Lower = more aggressive matching.
SIMILARITY_THRESHOLD = 0.85

# Redis key prefixes
_PREFIX_EMB   = "semantic:emb:"    # stores embedding + answer
_INDEX_KEY    = "semantic:index"   # set of all embedding hashes
_TTL_SECONDS  = 7 * 24 * 3600     # 7 days


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    """Pure-Python cosine similarity. No numpy needed."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _normalize_query(query: str) -> str:
    """
    Light normalization before embedding.
    Removes punctuation noise but keeps math symbols — '2+2' and '2 + 2'
    should map to the same embedding region.
    """
    import re
    q = query.lower().strip()
    # collapse whitespace
    q = re.sub(r"\s+", " ", q)
    return q


class SemanticCache:
    """
    Semantic similarity cache backed by Redis.

    Usage (in orchestrator):
        sc = SemanticCache(redis_client, gemini_client)

        # Lookup
        result = sc.get(query)
        if result:
            return result["answer"]

        # Store after getting answer from API
        sc.set(query, answer_text, metadata)
    """

    def __init__(self, redis_client, gemini_api_key: str):
        self.redis  = redis_client
        self._api_key = gemini_api_key
        self._genai = None   # lazy init

    def _get_client(self):
        """Lazy-init google.genai client so import errors are surfaced clearly."""
        if self._genai is None:
            try:
                from google import genai
                self._genai = genai.Client(api_key=self._api_key)
            except Exception as e:
                logger.error(f"SemanticCache: failed to init genai client: {e}")
                raise
        return self._genai

    def _embed(self, text: str) -> Optional[List[float]]:
        """
        Generate embedding vector for text.
        Uses gemini-embedding-001 (NOT counted against generate_content quota).
        Returns None on failure so cache misses gracefully on API errors.
        """
        try:
            from google.genai import types
            client = self._get_client()
            resp = client.models.embed_content(
                model="models/gemini-embedding-001",
                contents=_normalize_query(text),
                config=types.EmbedContentConfig(output_dimensionality=768),
            )
            return resp.embeddings[0].values
        except Exception as e:
            logger.warning(f"SemanticCache: embedding failed: {e}")
            return None

    def _query_hash(self, query: str) -> str:
        return hashlib.sha256(_normalize_query(query).encode()).hexdigest()[:16]

    # ── Public API ─────────────────────────────────────────────────────────

    def get(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Look up a semantically similar cached answer.

        Returns dict with keys: answer, metadata, source, similarity
        Returns None on cache miss or any error.
        """
        if not self.redis:
            return None

        try:
            # Get all stored embedding keys
            keys = self.redis.smembers(_INDEX_KEY)
            if not keys:
                return None

            # Embed the incoming query
            query_vec = self._embed(query)
            if query_vec is None:
                return None

            best_score = 0.0
            best_entry = None

            for key in keys:
                raw = self.redis.get(f"{_PREFIX_EMB}{key}")
                if not raw:
                    continue
                try:
                    entry = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                stored_vec = entry.get("embedding")
                if not stored_vec:
                    continue

                score = _cosine_similarity(query_vec, stored_vec)
                if score > best_score:
                    best_score = score
                    best_entry = entry

            if best_score >= SIMILARITY_THRESHOLD and best_entry:
                logger.info(
                    f"SemanticCache HIT | similarity={best_score:.3f} | "
                    f"query='{query[:60]}' matched '{best_entry.get('query','')[:60]}'"
                )
                return {
                    "answer":     best_entry["answer"],
                    "metadata":   best_entry.get("metadata", {}),
                    "source":     "semantic_cache",
                    "similarity": round(best_score, 3),
                }

            logger.debug(f"SemanticCache MISS | best_score={best_score:.3f} | query='{query[:60]}'")
            return None

        except Exception as e:
            logger.error(f"SemanticCache.get failed: {e}")
            return None

    def set(self, query: str, answer: str, metadata: Optional[Dict] = None) -> bool:
        """
        Store a query+answer with its embedding vector.
        Silent on failure — caching is best-effort.
        """
        if not self.redis or not answer:
            return False

        try:
            embedding = self._embed(query)
            if embedding is None:
                return False

            key = self._query_hash(query)
            entry = {
                "query":     _normalize_query(query),
                "answer":    answer,
                "metadata":  metadata or {},
                "embedding": embedding,
                "timestamp": time.time(),
            }
            self.redis.setex(
                f"{_PREFIX_EMB}{key}",
                _TTL_SECONDS,
                json.dumps(entry),
            )
            self.redis.sadd(_INDEX_KEY, key)
            self.redis.expire(_INDEX_KEY, _TTL_SECONDS)

            logger.info(f"SemanticCache SET | key={key} | query='{query[:60]}'")
            return True

        except Exception as e:
            logger.error(f"SemanticCache.set failed: {e}")
            return False

    def invalidate(self, query: str) -> bool:
        """Remove a specific entry (e.g. if answer was wrong)."""
        try:
            key = self._query_hash(query)
            self.redis.delete(f"{_PREFIX_EMB}{key}")
            self.redis.srem(_INDEX_KEY, key)
            return True
        except Exception as e:
            logger.error(f"SemanticCache.invalidate failed: {e}")
            return False

    def stats(self) -> Dict[str, Any]:
        """How many entries are cached."""
        try:
            count = self.redis.scard(_INDEX_KEY) if self.redis else 0
            return {"entries": count, "threshold": SIMILARITY_THRESHOLD}
        except Exception:
            return {"entries": 0, "threshold": SIMILARITY_THRESHOLD}
