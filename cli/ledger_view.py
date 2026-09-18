"""Read-only helpers on the ledger connection (bets of a fixture, closing presence)."""

from typing import Any, Dict, List


def fixture_bets(ledger: Any, fixture_id: int) -> List[Dict[str, Any]]:
    """Bets of a fixture as dicts (empty list on any failure)."""
    try:
        rows = ledger.conn.execute("SELECT * FROM ledger_bets WHERE fixture_id=? ORDER BY id",
                                   (fixture_id,)).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


def has_closing(ledger: Any, fixture_id: int) -> bool:
    """True if a 'close' snapshot is already stored for the fixture."""
    try:
        return ledger.conn.execute("SELECT 1 FROM ledger_snapshots WHERE fixture_id=? AND kind='close' "
                                   "LIMIT 1", (fixture_id,)).fetchone() is not None
    except Exception:
        return False
