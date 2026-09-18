"""Shared plumbing of the market_data layer: never-raising API access + cache.

Every market_data function goes through `api_get` (network/API errors become a
logged None, never an exception) and `cached` (SQLite cache, offline-safe).
Tests inject fakes with `set_client` / `set_cache`.
"""

import logging
from typing import Any, Awaitable, Callable, Dict, Optional

from utils import cache_manager

log = logging.getLogger("market_data")

_client: Optional[Any] = None
_cache: Optional[Any] = None


def set_client(client: Optional[Any]) -> None:
    """Inject an object exposing `async request(endpoint, params)` (tests)."""
    global _client
    _client = client


def set_cache(cache: Optional[Any]) -> None:
    """Inject a cache exposing async get_data/set_data (tests)."""
    global _cache
    _cache = cache


def get_client() -> Any:
    global _client
    if _client is None:
        from adapters.http_client import FootballHTTPClient  # lazy: no credentials at import
        _client = FootballHTTPClient()
    return _client


def get_cache() -> Optional[Any]:
    global _cache
    if _cache is None:
        try:
            _cache = cache_manager.get_cache()
        except Exception as exc:  # cache must never break the pipeline (rule 9)
            log.warning("cache unavailable: %s", exc)
    return _cache


async def api_get(endpoint: str, params: Dict[str, Any]) -> Optional[list]:
    """GET `endpoint`; return the `response` list, or None on any failure."""
    try:
        data = await get_client().request(endpoint, params)
        return data.get("response") or []
    except Exception as exc:
        log.warning("API %s %s failed: %s", endpoint, params, exc)
        return None


async def cached(key: str, ttl_type: str, loader: Callable[[], Awaitable[Optional[Any]]],
                 max_age: Optional[int] = None) -> Optional[Any]:
    """Cache-first wrapper. `loader` returning None (failure) is never cached.

    With `max_age` (seconds) the entry is stored with a timestamp and ignored
    once older than that, independently of the backend TTL (quotes: 600s).
    """
    import time
    cache = get_cache()
    if cache is not None:
        try:
            hit = await cache.get_data(key)
            if hit is not None:
                if max_age is None:
                    return hit["v"] if isinstance(hit, dict) and "v" in hit else hit
                if isinstance(hit, dict) and time.time() - hit.get("t", 0) <= max_age:
                    return hit["v"]
        except Exception as exc:
            log.warning("cache read failed (%s): %s", key, exc)
    value = await loader()
    if value is not None and cache is not None:
        try:
            await cache.set_data(key, {"t": time.time(), "v": value}, ttl_type)
        except Exception as exc:
            log.warning("cache write failed (%s): %s", key, exc)
    return value
