"""
Closing-line evaluation of the xG model against football-data.co.uk odds.

Two DIFFERENT things are measured here (do not confuse them):

1. ROI at the closing price (`roi_close`): betting our value selections at the
   CLOSING line and settling on real results. A realised-profit test, noisy on
   a few hundred bets. It is NOT Closing Line Value.
2. True CLV (`clv_odds`, `clv_fair`): for selections we would have TAKEN at the
   OPENING price of a book (EV > tau there), how much the price moved by the
   close, for the SAME book. It needs no results, so it is far less noisy:
     clv_odds = mean(open_odds / close_odds - 1)
     clv_fair = mean(fair_close_prob * open_odds - 1)   (close de-vigged)
   Positive = the market moved towards our side after we would have bet.

Value rule (rule 7): EV = P * odds - 1 > tau via core/edge_calculator.
Pairings whose goals/date disagree with the odds record are refused.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from backtest.metrics import brier_score_average
from backtest.odds_data import verify_match
from core.value_selection import ev_fraction


def _devig(*odds: float) -> Tuple[float, ...]:
    """De-vig decimal odds into fair probabilities that sum to 1."""
    inv = [1.0 / o for o in odds]
    s = sum(inv)
    return tuple(i / s for i in inv)


@dataclass
class MarketCLV:
    market: str
    n_matches: int          # matches with usable odds
    n_bets: int             # value selections backed at the closing line
    roi_close: float        # realised yield at the CLOSING price (profit / stake)
    our_brier: float        # our model's Brier on this market
    market_brier: float     # closing line's (de-vigged) Brier — the bar to beat
    avg_edge: float         # mean (our_prob - fair_market_prob) on backed bets
    n_clv_bets: int = 0     # selections taken at the opening price (same-book open+close)
    clv_odds: Optional[float] = None   # mean(open/close - 1)
    clv_fair: Optional[float] = None   # mean(fair_close_p * open - 1)


@dataclass
class CLVReport:
    season: int
    matched: int
    unmatched: int
    unmatched_pairs: List[Tuple[str, str]] = field(default_factory=list)
    rejected_pairs: List[Tuple[str, str]] = field(default_factory=list)  # goals/date mismatch
    markets: List[MarketCLV] = field(default_factory=list)


class _Acc:
    """Per-market accumulators."""

    def __init__(self, name: str):
        self.name = name
        self.n = 0
        self.profit, self.edges = [], []
        self.our, self.mkt = [], []
        self.clv_odds, self.clv_fair = [], []

    def add(self, prices, opens, our_probs, outcomes, tau):
        """One match: prices = closing odds per selection; opens = opening odds or None."""
        self.n += 1
        fair = _devig(*prices)
        for i, (odd, our_p, won) in enumerate(zip(prices, our_probs, outcomes)):
            self.our.append((our_p, int(won)))
            self.mkt.append((fair[i], int(won)))
            if ev_fraction(our_p, odd) > tau:
                self.profit.append((odd - 1.0) if won else -1.0)
                self.edges.append(our_p - fair[i])
            if opens and ev_fraction(our_p, opens[i]) > tau:
                self.clv_odds.append(opens[i] / odd - 1.0)
                self.clv_fair.append(fair[i] * opens[i] - 1.0)

    def result(self) -> MarketCLV:
        def avg(xs, nd=4):
            return round(sum(xs) / len(xs), nd) if xs else None
        return MarketCLV(
            market=self.name, n_matches=self.n, n_bets=len(self.profit),
            roi_close=avg(self.profit) or 0.0,
            our_brier=brier_score_average(self.our) if self.our else 0.0,
            market_brier=brier_score_average(self.mkt) if self.mkt else 0.0,
            avg_edge=avg(self.edges) or 0.0,
            n_clv_bets=len(self.clv_odds), clv_odds=avg(self.clv_odds),
            clv_fair=avg(self.clv_fair),
        )


def _line(odds: Dict, keys: Tuple[str, ...]):
    vals = tuple(odds.get(k) for k in keys)
    return vals if all(vals) else None


def evaluate_clv(
    predictions: List[Dict],
    odds_index: Dict[tuple, Dict],
    *,
    ev_threshold: float = 0.0,
) -> CLVReport:
    """
    predictions: from iter_xg_predictions.
    odds_index:  from odds_data.index_by_teams.
    ev_threshold: minimum EV (our_prob * odds - 1) to place a bet.
    """
    unmatched_pairs, rejected = [], []
    matched = 0
    x_acc, ou_acc = _Acc("Risultato 1X2"), _Acc("Over/Under 2.5")

    for pred in predictions:
        key = (pred["home_name"], pred["away_name"])
        odds = odds_index.get(key)
        if odds is None:
            unmatched_pairs.append(key)
            continue
        if not verify_match(pred, odds):
            unmatched_pairs.append(key)
            rejected.append(key)
            continue
        matched += 1
        p = pred["probs"]
        hg, ag = pred["home_goals"], pred["away_goals"]

        close = _line(odds, ("o1", "ox", "o2"))
        if close:
            res = "1" if hg > ag else "2" if hg < ag else "X"
            x_acc.add(close, _line(odds, ("open_o1", "open_ox", "open_o2")),
                      (p["result_1"], p["result_X"], p["result_2"]),
                      (res == "1", res == "X", res == "2"), ev_threshold)

        close = _line(odds, ("oover", "ounder"))
        if close:
            over = (hg + ag) > 2.5
            ou_acc.add(close, _line(odds, ("open_oover", "open_ounder")),
                       (p["over_2_5"], 1.0 - p["over_2_5"]),
                       (over, not over), ev_threshold)

    return CLVReport(
        season=0, matched=matched, unmatched=len(unmatched_pairs),
        unmatched_pairs=unmatched_pairs, rejected_pairs=rejected,
        markets=[x_acc.result(), ou_acc.result()],
    )
