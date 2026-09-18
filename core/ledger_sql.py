"""Connection, DDL loading and time helpers of the paper-trading ledger."""

import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_LEDGER_PATH = "data/footy_predictor.db"
_DDL_RE = re.compile(r"-- BEGIN ledger\n(.*?)-- END ledger", re.S)


def load_ledger_ddl() -> str:
    """Ledger DDL from database/schema.sql (SSOT), between the ledger markers."""
    schema = (Path(__file__).parent.parent / "database" / "schema.sql").read_text(encoding="utf-8")
    match = _DDL_RE.search(schema)
    if not match:
        raise RuntimeError("ledger section missing in database/schema.sql")
    return match.group(1)


def connect(path: str) -> sqlite3.Connection:
    """SQLite connection with WAL + busy_timeout; DDL applied idempotently."""
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 10000")
    if path != ":memory:":
        conn.execute("PRAGMA journal_mode = WAL")
    conn.executescript(load_ledger_ddl())
    return conn


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).isoformat(timespec="seconds")
