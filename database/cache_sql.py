"""SQL condiviso per la tabella api_cache (usato da DatabaseManager async e da utils/sqlite_cache.py sync)."""

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

TS_FORMAT = "%Y-%m-%d %H:%M:%S"  # UTC, ordinabile come stringa

SQL_GET = "SELECT value, expires_at FROM api_cache WHERE key = ?"
SQL_SET = ("INSERT INTO api_cache (key, value, ttl_type, expires_at, created_at) VALUES (?, ?, ?, ?, ?) "
           "ON CONFLICT(key) DO UPDATE SET value=excluded.value, ttl_type=excluded.ttl_type, "
           "expires_at=excluded.expires_at, created_at=excluded.created_at")
SQL_DELETE = "DELETE FROM api_cache WHERE key = ?"
SQL_CLEANUP = "DELETE FROM api_cache WHERE expires_at IS NOT NULL AND expires_at <= ?"

_DDL_RE = re.compile(r"-- BEGIN api_cache\n(.*?)-- END api_cache", re.S)


def load_api_cache_ddl() -> str:
    """Estrae le istruzioni api_cache da database/schema.sql (SSOT)."""
    schema = (Path(__file__).parent / "schema.sql").read_text(encoding="utf-8")
    match = _DDL_RE.search(schema)
    if not match:
        raise RuntimeError("Sezione api_cache mancante in database/schema.sql")
    return match.group(1)


def fmt_ts(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime(TS_FORMAT)


def compute_expiry(ttl: int, now: datetime) -> Optional[str]:
    """expires_at per un TTL in secondi; ttl <= 0 (-1) = permanente (None)."""
    return None if ttl is None or ttl <= 0 else fmt_ts(now + timedelta(seconds=ttl))


def is_expired(expires_at: Optional[str], now: datetime) -> bool:
    return expires_at is not None and expires_at <= fmt_ts(now)
