"""Odds cache: in-process TTL dict backed by Redis, degrading silently offline.

Redis being down (or raising) must never propagate: the in-memory layer keeps
working and the caller just gets a miss.
"""

import time
from typing import Any, Dict, Tuple

from core.odds_markets import ODDS_CACHE_TTL

_MISS = object()


class OddsCache:
    """TTL cache. Age is checked on read, so the Redis-side TTL (30 min) is irrelevant."""

    def __init__(self, redis_cache=None, ttl: int = ODDS_CACHE_TTL):
        self._redis = redis_cache
        self._ttl = ttl
        self._memory: Dict[str, Tuple[float, Any]] = {}

    async def get(self, key: str) -> Any:
        """Return the cached value, or OddsCache.MISS."""
        now = time.time()
        entry = self._memory.get(key)
        if entry is not None:
            if now - entry[0] <= self._ttl:
                return entry[1]
            del self._memory[key]

        if self._redis is None:
            return self.MISS
        try:
            stored = await self._redis.get_data(key)
        except Exception:
            return self.MISS
        if isinstance(stored, dict) and "_cached_at" in stored and "data" in stored:
            if now - stored["_cached_at"] <= self._ttl:
                self._memory[key] = (stored["_cached_at"], stored["data"])
                return stored["data"]
        return self.MISS

    async def set(self, key: str, value: Any) -> None:
        """Store `value` (JSON-serialisable). Never raises."""
        now = time.time()
        self._memory[key] = (now, value)
        if self._redis is None:
            return
        try:
            await self._redis.set_data(key, {"_cached_at": now, "data": value}, ttl_type="live_odds")
        except Exception:
            pass

    MISS = _MISS
