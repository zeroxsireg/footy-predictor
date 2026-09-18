"""Read-only statistics and calibration over the ledger tables."""

import json
import math
import sqlite3
from typing import Dict, List, Optional

from backtest.metrics import rps_1x2

from .contracts import MARKET_1X2, MARKET_OU25
from .devig import shin
from .value_selection import INITIAL_BANKROLL


def _mean(xs: List[float]) -> Optional[float]:
    return sum(xs) / len(xs) if xs else None


def strategy_stats(conn: sqlite3.Connection, strategy: str) -> Dict[str, Optional[float]]:
    rows = conn.execute("SELECT * FROM ledger_bets WHERE strategy=? AND status IN ('won','lost') "
                        "ORDER BY settled_at, id", (strategy,)).fetchall()
    staked = sum(r["stake_amount"] for r in rows)
    profit = sum(r["profit"] for r in rows)
    equity, peak, max_dd = INITIAL_BANKROLL, INITIAL_BANKROLL, 0.0
    for r in rows:
        equity += r["profit"]
        peak = max(peak, equity)
        max_dd = max(max_dd, (peak - equity) / peak if peak > 0 else 0.0)
    return {
        "n_bets": len(rows),
        "roi": profit / staked if staked else None,
        "hit_rate": sum(r["status"] == "won" for r in rows) / len(rows) if rows else None,
        "profit": profit,
        "max_drawdown": max_dd,
        "avg_clv": _mean([r["clv"] for r in rows if r["clv"] is not None]),
        "n_open": conn.execute("SELECT COUNT(*) FROM ledger_bets WHERE strategy=? AND status='open'",
                               (strategy,)).fetchone()[0],
    }


def _close_odds(conn: sqlite3.Connection, fixture_id: int, market: str) -> Optional[Dict[str, float]]:
    row = conn.execute("SELECT odds_json FROM ledger_snapshots WHERE fixture_id=? AND market=? "
                       "AND kind='close' ORDER BY id DESC LIMIT 1", (fixture_id, market)).fetchone()
    return json.loads(row["odds_json"]) if row else None


def _outcome(h: int, a: int) -> str:
    return "1" if h > a else ("2" if a > h else "X")


def _players(conn: sqlite3.Connection, k: int) -> Dict[str, Optional[float]]:
    rows = conn.execute("SELECT fixture_id, p_booked, booked FROM ledger_player_predictions "
                        "WHERE booked IS NOT NULL").fetchall()
    by_fx: Dict[int, list] = {}
    for r in rows:
        by_fx.setdefault(r["fixture_id"], []).append((r["p_booked"], r["booked"]))
    prec = []
    for items in by_fx.values():
        top = sorted(items, key=lambda t: t[0], reverse=True)[:k]
        prec.append(sum(b for _, b in top) / len(top))
    return {"n": len(rows), "brier": _mean([(p - b) ** 2 for p, b in
                                            [(r["p_booked"], r["booked"]) for r in rows]]),
            "precision_at_k": _mean(prec), "k": k}


def calibration(conn: sqlite3.Connection, k: int = 3) -> Dict[str, object]:
    """Model vs Shin(closing) on settled fixtures having prediction + closing quote."""
    preds = conn.execute("SELECT p.*, r.home_goals, r.away_goals FROM ledger_predictions p "
                         "JOIN ledger_results r USING (fixture_id)").fetchall()
    rps_m, rps_k, br_m, br_k, o_m, o_k = [], [], [], [], [], []
    for p in preds:
        out = _outcome(p["home_goals"], p["away_goals"])
        c1 = _close_odds(conn, p["fixture_id"], MARKET_1X2)
        if c1 and all(s in c1 for s in "1X2"):
            fair = dict(zip("1X2", shin([c1[s] for s in "1X2"])))
            rps_m.append(rps_1x2({"1": p["p1"], "X": p["px"], "2": p["p2"]}, out))
            rps_k.append(rps_1x2(fair, out))
            br_m.append(sum((q - (s == out)) ** 2 for s, q in zip("1X2", (p["p1"], p["px"], p["p2"]))))
            br_k.append(sum((fair[s] - (s == out)) ** 2 for s in "1X2"))
        c2 = _close_odds(conn, p["fixture_id"], MARKET_OU25)
        if c2 and "over" in c2 and "under" in c2:
            over = int(p["home_goals"] + p["away_goals"] > 2.5)
            o_m.append((p["p_over_2_5"] - over) ** 2)
            o_k.append((shin([c2["over"], c2["under"]])[0] - over) ** 2)
    return {"n_1x2": len(rps_m), "rps_model": _mean(rps_m), "rps_market": _mean(rps_k),
            "brier_1x2_model": _mean(br_m), "brier_1x2_market": _mean(br_k),
            "n_ou25": len(o_m), "brier_over_model": _mean(o_m), "brier_over_market": _mean(o_k),
            "players": _players(conn, k)}
