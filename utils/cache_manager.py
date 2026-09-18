"""Selettore del backend di cache (CACHE_BACKEND = sqlite | redis | auto).

Default sqlite: funziona out-of-the-box, niente demoni. Redis solo se richiesto
esplicitamente e raggiungibile; in ogni altro caso si ricade su SQLite con al
massimo UNA riga informativa per processo.
"""

import socket
from pathlib import Path
from typing import Any, Optional

_cache: Optional[Any] = None
_announced = False


def _info_once(message: str) -> None:
    global _announced
    if not _announced:
        _announced = True
        print(message)


def _redis_reachable(host: str, port: int, timeout: float = 2.0) -> bool:
    if not host:
        return False
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def build_cache(backend: str, db_path: str, redis_host: str = "", redis_port: int = 6379):
    """Costruisce la cache per `backend`; non tocca il singleton globale."""
    backend = (backend or "sqlite").lower()
    if backend in ("redis", "auto"):
        if _redis_reachable(redis_host, redis_port):
            from utils.redis_cache import _get_redis_backend
            cache = _get_redis_backend()
            if cache.is_connected():
                return cache
        _info_once(f"ℹ️  Redis non raggiungibile: uso la cache SQLite locale ({db_path})")
    from utils.sqlite_cache import SqliteFootballCache
    return SqliteFootballCache(db_path)


def get_cache():
    """Singleton di processo della cache dell'app."""
    global _cache
    if _cache is None:
        from core.config import get_settings
        settings = get_settings()
        db_path = settings.cache_db_path
        if db_path != ":memory:" and not Path(db_path).is_absolute():
            db_path = str(Path(__file__).resolve().parent.parent / db_path)  # ancorato alla root del progetto
        _cache = build_cache(settings.cache_backend, db_path,
                             settings.redis_host, settings.redis_port)
    return _cache


def reset_cache() -> None:
    """Dimentica il singleton (test / cambio configurazione)."""
    global _cache, _announced
    _cache, _announced = None, False
