"""
Closing Line Value / edge evaluation against the market.

Joins the xG model's predictions with football-data.co.uk closing odds and asks
the only question that matters for profitability: **betting our model's value
selections at the closing (Pinnacle) line, do we make money?**

Positive realised ROI vs the closing line = a genuine edge. Negative = the small
skill we measured does not beat the market's margin (the research's expectation
for efficient top-league markets).
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from backtest.metrics import brier_score_average


def _devig(*odds: float) -> Tuple[float, ...]:
    """De-vig decimal odds into fair probabilities that sum to 1."""
    inv = [1.0 / o for o in odds]
    s = sum(inv)
    return tuple(i / s for i in inv)


@dataclass
class MarketCLV:
    market: str
    n_matches: int          # matches with usable odds
    n_bets: int             # value selections backed
    roi: float              # realised yield vs closing line (profit / stake)
    our_brier: float        # our model's Brier on this market
    market_brier: float     # closing line's (de-vigged) Brier — the bar to beat
    avg_edge: float         # mean (our_prob - fair_market_prob) on backed bets


@dataclass
class CLVReport:
    season: int
    matched: int
    unmatched: int
    unmatched_pairs: List[Tuple[str, str]] = field(default_factory=list)
    markets: List[MarketCLV] = field(default_factory=list)


def _settle(profit_list, won: bool, odds: float):
    profit_list.append((odds - 1.0) if won else -1.0)


def evaluate_clv(
    predictions: List[Dict],
    odds_index: Dict[tuple, Dict],
    *,
    edge_threshold: float = 0.0,
) -> CLVReport:
    """
    predictions: from iter_xg_predictions.
    odds_index:  from odds_data.index_by_teams.
    edge_threshold: minimum EV edge (our_prob*odds - 1) to place a bet.
    """
    matched = 0
    unmatched_pairs = []

    # 1X2 accumulators
    x_profit, x_edges = [], []
    x_our, x_mkt = [], []      # (prob, outcome) for Brier
    # Over/Under 2.5 accumulators
    o_profit, o_edges = [], []
    o_our, o_mkt = [], []
    n_1x2_matches = n_ou_matches = 0

    for pred in predictions:
        key = (pred["home_name"], pred["away_name"])
        odds = odds_index.get(key)
        if odds is None:
            unmatched_pairs.append(key)
            continue
        matched += 1
        p = pred["probs"]
        hg, ag = pred["home_goals"], pred["away_goals"]

        # ── 1X2 ──
        o1, ox, o2 = odds.get("o1"), odds.get("ox"), odds.get("o2")
        if o1 and ox and o2:
            n_1x2_matches += 1
            fair = _devig(o1, ox, o2)
            result = "1" if hg > ag else "2" if hg < ag else "X"
            for sel, odd, our_p, fair_p, oc in [
                ("1", o1, p["result_1"], fair[0], result == "1"),
                ("X", ox, p["result_X"], fair[1], result == "X"),
                ("2", o2, p["result_2"], fair[2], result == "2"),
            ]:
                x_our.append((our_p, 1 if oc else 0))
                x_mkt.append((fair_p, 1 if oc else 0))
                if our_p * odd - 1.0 > edge_threshold:
                    _settle(x_profit, oc, odd)
                    x_edges.append(our_p - fair_p)

        # ── Over/Under 2.5 ──
        oover, ounder = odds.get("oover"), odds.get("ounder")
        if oover and ounder:
            n_ou_matches += 1
            fair_o, fair_u = _devig(oover, ounder)
            over = (hg + ag) > 2.5
            p_over = p["over_2_5"]
            p_under = 1.0 - p_over
            o_our.append((p_over, 1 if over else 0))
            o_mkt.append((fair_o, 1 if over else 0))
            for our_p, fair_p, odd, oc in [
                (p_over, fair_o, oover, over),
                (p_under, fair_u, ounder, not over),
            ]:
                if our_p * odd - 1.0 > edge_threshold:
                    _settle(o_profit, oc, odd)
                    o_edges.append(our_p - fair_p)

    def market(name, profit, edges, our, mkt, n):
        return MarketCLV(
            market=name,
            n_matches=n,
            n_bets=len(profit),
            roi=round(sum(profit) / len(profit), 4) if profit else 0.0,
            our_brier=brier_score_average(our) if our else 0.0,
            market_brier=brier_score_average(mkt) if mkt else 0.0,
            avg_edge=round(sum(edges) / len(edges), 4) if edges else 0.0,
        )

    return CLVReport(
        season=0,
        matched=matched,
        unmatched=len(unmatched_pairs),
        unmatched_pairs=unmatched_pairs,
        markets=[
            market("Risultato 1X2", x_profit, x_edges, x_our, x_mkt, n_1x2_matches),
            market("Over/Under 2.5", o_profit, o_edges, o_our, o_mkt, n_ou_matches),
        ],
    )
