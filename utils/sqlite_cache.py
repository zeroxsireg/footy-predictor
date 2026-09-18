"""Cache persistente su SQLite (drop-in per RedisFootballCache), senza demoni.

- File `data/footy_predictor.db` (WAL) oppure `:memory:` (una sola connessione condivisa).
- Sync: get_team_roster & co. sono chiamate SINCRONE nel codice esistente -> sqlite3 stdlib
  con UNA connessione (check_same_thread=False) protetta da RLock + busy_timeout.
- Async: get_data/set_data/get_cache_info... restano `async def` (chi le usa fa `await`),
  ma eseguono le stesse operazioni sincrone locali (microsecondi).
- Mai eccezioni verso il chiamante: un errore SQLite = miss / False.
"""

import logging
import os
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from database import cache_sql
from utils import cache_codec
from utils.cache_ttl import ttl_seconds
from utils.football_cache_mixin import FootballCacheMixin

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = "data/footy_predictor.db"


class SqliteFootballCache(FootballCacheMixin):
    """Cache locale con TTL per ttl_type (mappa in utils/cache_ttl.py)."""

    backend = "sqlite"

    def __init__(self, db_path: str = DEFAULT_DB_PATH, clock: Optional[Callable[[], datetime]] = None):
        self.db_path = db_path
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._lock = threading.RLock()
        self._conn: Optional[sqlite3.Connection] = None
        self.stats = {"hits": 0, "misses": 0, "expired": 0, "writes": 0}
        try:
            self._open()
            self.cache_cleanup_expired()
        except Exception as exc:  # cache disattiva, mai crash
            logger.warning("Cache SQLite non disponibile: %s", exc)
            self._conn = None

    def _open(self) -> None:
        if self.db_path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=10)
        conn.execute("PRAGMA busy_timeout = 10000")
        if self.db_path != ":memory:":
            conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.executescript(cache_sql.load_api_cache_ddl())
        conn.commit()
        self._conn = conn

    def _now(self) -> datetime:
        return self._clock()

    def is_connected(self) -> bool:
        """True quando il backend SQLite e' operativo."""
        return self._conn is not None

    # ── core key/value ───────────────────────────────────────────────────────

    def _get_with_decompression(self, key: str) -> Optional[Any]:
        if self._conn is None:
            return None
        try:
            with self._lock:
                row = self._conn.execute(cache_sql.SQL_GET, (key,)).fetchone()
                if row is None:
                    self.stats["misses"] += 1
                    return None
                if cache_sql.is_expired(row[1], self._now()):
                    self._conn.execute(cache_sql.SQL_DELETE, (key,))
                    self._conn.commit()
                    self.stats["expired"] += 1
                    self.stats["misses"] += 1
                    return None
            value = cache_codec.decode(row[0])
            self.stats["hits"] += 1
            return value
        except Exception as exc:
            logger.debug("cache get %s fallita: %s", key, exc)
            return None

    def _set_with_ttl(self, key: str, data: Any, ttl_type: str, compress: bool = True) -> bool:
        if self._conn is None:
            return False
        try:
            now = self._now()
            payload = cache_codec.encode(data, compress)
            with self._lock:
                self._conn.execute(cache_sql.SQL_SET, (key, payload, ttl_type,
                                                       cache_sql.compute_expiry(ttl_seconds(ttl_type), now),
                                                       cache_sql.fmt_ts(now)))
                self._conn.commit()
            self.stats["writes"] += 1
            return True
        except Exception as exc:
            logger.debug("cache set %s fallita: %s", key, exc)
            return False

    def delete_data(self, key: str) -> bool:
        if self._conn is None:
            return False
        try:
            with self._lock:
                cur = self._conn.execute(cache_sql.SQL_DELETE, (key,))
                self._conn.commit()
            return cur.rowcount > 0
        except Exception:
            return False

    def cache_cleanup_expired(self) -> int:
        """Elimina le entry scadute; ritorna quante."""
        if self._conn is None:
            return 0
        try:
            with self._lock:
                cur = self._conn.execute(cache_sql.SQL_CLEANUP, (cache_sql.fmt_ts(self._now()),))
                self._conn.commit()
            return cur.rowcount
        except Exception:
            return 0

    def _keys_like(self, pattern: str) -> List[str]:
        if self._conn is None:
            return []
        try:
            with self._lock:
                rows = self._conn.execute(
                    "SELECT key FROM api_cache WHERE key LIKE ? AND (expires_at IS NULL OR expires_at > ?)",
                    (pattern, cache_sql.fmt_ts(self._now()))).fetchall()
            return [r[0] for r in rows]
        except Exception:
            return []

    # ── API async (stessa firma di RedisFootballCache) ───────────────────────

    async def set_data(self, key: str, data: Any, ttl_type: str) -> bool:
        return self._set_with_ttl(key, data, ttl_type)

    async def get_data(self, key: str, ttl_type: str = None) -> Optional[Any]:
        return self._get_with_decompression(key)

    async def clear_all_cache(self):
        if self._conn is None:
            raise Exception("Cache SQLite non disponibile")
        with self._lock:
            self._conn.execute("DELETE FROM api_cache")
            self._conn.commit()

    async def get_sample_keys(self, limit: int = 10) -> List[str]:
        return self._keys_like("%")[:limit]

    async def get_cache_info(self) -> Dict[str, Any]:
        if self._conn is None:
            return {"error": "Cache SQLite non disponibile"}
        mem = self.get_memory_usage()
        return {"total_keys": mem["keys_count"], "used_memory": mem["used_memory_human"],
                "uptime": "n/a (SQLite, nessun demone)", "backend": "sqlite", **self.stats}

    # ── diagnostica ──────────────────────────────────────────────────────────

    def get_memory_usage(self) -> Dict[str, Any]:
        """Numero chiavi e dimensione del file (nomi campo compatibili con la CLI)."""
        if self._conn is None:
            return {"error": "Not connected"}
        try:
            with self._lock:
                keys = self._conn.execute("SELECT COUNT(*) FROM api_cache").fetchone()[0]
                size = self._conn.execute("SELECT SUM(LENGTH(value)) FROM api_cache").fetchone()[0] or 0
            if self.db_path != ":memory:" and os.path.exists(self.db_path):
                size = os.path.getsize(self.db_path)
            return {"keys_count": keys, "used_memory_mb": round(size / (1024 * 1024), 2),
                    "used_memory_human": f"{size / 1024:.1f} KB", "size_bytes": size}
        except Exception as exc:
            return {"error": str(exc)}

    def get_key_info(self, key: str) -> Dict:
        if self._conn is None:
            return {}
        with self._lock:
            row = self._conn.execute(cache_sql.SQL_GET, (key,)).fetchone()
        if row is None:
            return {}
        data = self._get_with_decompression(key)
        return {"key": key, "expires_at": row[1], "is_permanent": row[1] is None,
                "metadata": data.get("_metadata", {}) if isinstance(data, dict) else {},
                "is_historical": self.is_historical_data(data) if data else False}

    def health_check(self) -> Dict[str, Any]:
        if self._conn is None:
            return {"status": "disconnected", "error": "Cache SQLite non disponibile", "backend": "sqlite"}
        try:
            with self._lock:
                self._conn.execute("SELECT 1").fetchone()
            return {"status": "healthy", "backend": "sqlite", "connection": "ok", "path": self.db_path,
                    "memory_usage": self.get_memory_usage(), "stats": dict(self.stats)}
        except Exception as exc:
            return {"status": "error", "error": str(exc), "backend": "sqlite"}

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None
