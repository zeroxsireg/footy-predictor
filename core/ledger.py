"""
Forward ledger (paper trading) on SQLite. No network access.

NULL p_model in ledger_bets = model-free strategy (sharp_gap); readers must ignore it.

Tables `ledger_*` live in database/schema.sql (between the ledger markers). Every
strategy has its own bankroll (INITIAL_BANKROLL). Bankroll changes only at settlement.
"""

import json
import math
from typing import Dict, Iterable, List, Optional

from .contracts import (MARKET_1X2, MARKET_OU25, BetCandidate, FixtureResult, MatchProbs,
                        PlayerCandidate, PriceQuote)
from .devig import shin
from .ledger_sql import DEFAULT_LEDGER_PATH, connect, iso, now_iso
from .ledger_stats import calibration, strategy_stats
from .value_engine import SELECTIONS, BankrollState
from .value_selection import INITIAL_BANKROLL

KINDS = ("pick", "close", "benchmark_pick", "benchmark_close")


def _wins(market: str, selection: str, home: int, away: int) -> bool:
    if market == MARKET_1X2:
        return selection == ("1" if home > away else "2" if away > home else "X")
    over = home + away > 2.5
    return selection == ("over" if over else "under")


class Ledger:
    def __init__(self, path: str = DEFAULT_LEDGER_PATH):
        self.conn = connect(path)

    def close(self) -> None:
        self.conn.close()

    # --- writes -----------------------------------------------------------
    def record_predictions(self, probs: Iterable[MatchProbs]) -> None:
        """All predicted fixtures (needed by calibration). Existing rows are kept."""
        with self.conn:
            self.conn.executemany(
                "INSERT OR IGNORE INTO ledger_predictions VALUES (?,?,?,?,?,?,?)",
                [(p.fixture_id, p.model, p.p1, p.px, p.p2, p.p_over_2_5, now_iso()) for p in probs])

    def record_player_predictions(self, cands: Iterable[PlayerCandidate]) -> None:
        with self.conn:
            self.conn.executemany(
                "INSERT OR IGNORE INTO ledger_player_predictions (fixture_id, player_id, name, team, "
                "p_given, start_prob, p_booked, created_at) VALUES (?,?,?,?,?,?,?,?)",
                [(c.fixture_id, c.player_id, c.name, c.team, c.p_booked_given_plays,
                  c.start_prob, c.p_booked, now_iso()) for c in cands])

    def record_snapshot(self, quote: PriceQuote, kind: str) -> None:
        if kind not in KINDS:
            raise ValueError(f"bad snapshot kind {kind}")
        with self.conn:
            self.conn.execute(
                "INSERT INTO ledger_snapshots (fixture_id, market, bookmaker, bookmaker_id, odds_json, "
                "kind, captured_at) VALUES (?,?,?,?,?,?,?)",
                (quote.fixture_id, quote.market, quote.bookmaker, quote.bookmaker_id,
                 json.dumps(quote.odds), kind, iso(quote.captured_at)))

    def record_closing(self, fixture_id: int, quotes: Dict[str, PriceQuote],
                       benchmark: Dict[str, PriceQuote]) -> None:
        for q in quotes.values():
            self.record_snapshot(q, "close")
        for q in benchmark.values():
            self.record_snapshot(q, "benchmark_close")

    def record_bets(self, bets: Iterable[BetCandidate]) -> int:
        """Idempotent on (strategy, fixture, market, selection). Returns rows inserted."""
        n = 0
        with self.conn:
            for b in bets:
                p_model = None if math.isnan(b.p_model) else b.p_model
                cur = self.conn.execute(
                    "INSERT OR IGNORE INTO ledger_bets (strategy, fixture_id, market, selection, odds, "
                    "bookmaker, p_model, p_used, p_fair, ev, stake_amount, stake_fraction, created_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (b.strategy, b.fixture_id, b.market, b.selection, b.odds, b.bookmaker, p_model,
                     b.p_used, b.p_fair, b.ev, b.stake_amount, b.stake_fraction,
                     iso(b.created_at) if b.created_at else now_iso()))
                n += cur.rowcount
        return n

    # --- settlement -------------------------------------------------------
    def _closing_clv(self, bet) -> tuple:
        """(closing_odds, clv) from the close snapshot of the SAME bookmaker, if present."""
        row = self.conn.execute(
            "SELECT odds_json FROM ledger_snapshots WHERE fixture_id=? AND market=? AND bookmaker=? "
            "AND kind='close' ORDER BY id DESC LIMIT 1",
            (bet["fixture_id"], bet["market"], bet["bookmaker"])).fetchone()
        if not row:
            return None, None
        odds = json.loads(row["odds_json"])
        sels = SELECTIONS[bet["market"]]
        if any(s not in odds for s in sels) or bet["selection"] not in sels:
            return None, None
        fair = shin([odds[s] for s in sels])[sels.index(bet["selection"])]
        return odds[bet["selection"]], bet["odds"] / (1.0 / fair) - 1.0

    def settle_fixture(self, result: FixtureResult) -> int:
        """Settle open bets of a finished fixture; updates bankroll and high-water mark."""
        if not result.finished:
            return 0
        h, a, ts = result.home_goals, result.away_goals, now_iso()
        bets = self.conn.execute("SELECT * FROM ledger_bets WHERE fixture_id=? AND status='open' "
                                 "ORDER BY id", (result.fixture_id,)).fetchall()
        with self.conn:
            self.conn.execute("INSERT OR REPLACE INTO ledger_results VALUES (?,?,?,?)",
                              (result.fixture_id, h, a, ts))
            for b in bets:
                won = _wins(b["market"], b["selection"], h, a)
                profit = b["stake_amount"] * (b["odds"] - 1.0) if won else -b["stake_amount"]
                c_odds, clv = self._closing_clv(b)
                self.conn.execute(
                    "UPDATE ledger_bets SET status=?, profit=?, closing_odds=?, clv=?, settled_at=? "
                    "WHERE id=?", ("won" if won else "lost", profit, c_odds, clv, ts, b["id"]))
                cur = self._stored_state(b["strategy"])
                self._save_state(b["strategy"], cur.after_update(cur.bankroll + profit), ts)
        return len(bets)

    def settle_players(self, fixture_id: int, booked_ids: Iterable[int]) -> None:
        booked = set(booked_ids)
        rows = self.conn.execute("SELECT player_id FROM ledger_player_predictions WHERE fixture_id=?",
                                 (fixture_id,)).fetchall()
        with self.conn:
            self.conn.executemany(
                "UPDATE ledger_player_predictions SET booked=?, settled_at=? WHERE fixture_id=? "
                "AND player_id=?", [(int(r["player_id"] in booked), now_iso(), fixture_id,
                                     r["player_id"]) for r in rows])

    # --- reads ------------------------------------------------------------
    def _save_state(self, strategy: str, st: BankrollState, ts: str) -> None:
        self.conn.execute(
            "INSERT INTO ledger_bankroll VALUES (?,?,?,?) ON CONFLICT(strategy) DO UPDATE SET "
            "bankroll=excluded.bankroll, high_water_mark=excluded.high_water_mark, "
            "updated_at=excluded.updated_at", (strategy, st.bankroll, st.high_water_mark, ts))

    def _stored_state(self, strategy: str) -> BankrollState:
        r = self.conn.execute("SELECT bankroll, high_water_mark FROM ledger_bankroll WHERE strategy=?",
                              (strategy,)).fetchone()
        if not r:
            return BankrollState(INITIAL_BANKROLL, INITIAL_BANKROLL)
        return BankrollState(r["bankroll"], r["high_water_mark"])

    def bankroll_state(self, strategy: str) -> BankrollState:
        st = self._stored_state(strategy)
        # breaker latch is derived by replaying settled profits (no extra column needed)
        replay = BankrollState()
        for p in self.conn.execute("SELECT profit FROM ledger_bets WHERE strategy=? AND status IN "
                                   "('won','lost') ORDER BY settled_at, id", (strategy,)):
            replay = replay.after_update(replay.bankroll + p["profit"])
        st.breaker_active = replay.breaker_active
        return st

    def bets_for_fixtures(self, strategy: str, fixture_ids: Iterable[int]) -> List[dict]:
        """Registered bets of a strategy on the given fixtures (for per-day limits)."""
        ids = list(fixture_ids)
        if not ids:
            return []
        marks = ",".join("?" * len(ids))
        rows = self.conn.execute(
            f"SELECT fixture_id, market, selection, stake_amount, status FROM ledger_bets "
            f"WHERE strategy=? AND fixture_id IN ({marks}) ORDER BY id", [strategy, *ids])
        return [dict(r) for r in rows]

    def open_fixtures(self) -> List[int]:
        return [r[0] for r in self.conn.execute(
            "SELECT DISTINCT fixture_id FROM ledger_bets WHERE status='open' ORDER BY fixture_id")]

    def unsettled_fixtures(self) -> List[int]:
        """Fixtures with a prediction, an open bet or player predictions, still without result."""
        return [r[0] for r in self.conn.execute(
            "SELECT fixture_id FROM ledger_predictions UNION "
            "SELECT fixture_id FROM ledger_bets WHERE status='open' UNION "
            "SELECT fixture_id FROM ledger_player_predictions WHERE booked IS NULL "
            "EXCEPT SELECT fixture_id FROM ledger_results ORDER BY 1")]

    def stats(self, strategy: str) -> Dict[str, Optional[float]]:
        return strategy_stats(self.conn, strategy)

    def calibration(self, k: int = 3) -> Dict[str, object]:
        return calibration(self.conn, k)
