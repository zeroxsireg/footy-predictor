"""
Backtest orchestration: replay -> predict -> score -> report.

Pure functions here (run_backtest) so they're easy to unit-test; the pretty
printing lives in report_text() and the CLI in run_backtest.py at repo root.
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple

from backtest.engine import iter_scored_matches, predict_match
from backtest.metrics import (
    BinaryMarketResult,
    MulticlassMarketResult,
    score_binary,
    score_multiclass,
)

# Binary markets: label -> (prediction key, outcome function name on ScoredMatch)
_BINARY_MARKETS = {
    "Over 1.5 Goals": "over_1_5",
    "Over 2.5 Goals": "over_2_5",
    "Over 3.5 Goals": "over_3_5",
    "BTTS Yes": "btts_yes",
}


@dataclass
class BacktestReport:
    league_id: int
    season: int
    min_matches: int
    total_matches_scored: int
    binary: List[BinaryMarketResult]
    result_1x2: MulticlassMarketResult


def _outcome(match, key: str) -> int:
    if key == "over_1_5":
        return match.over(1.5)
    if key == "over_2_5":
        return match.over(2.5)
    if key == "over_3_5":
        return match.over(3.5)
    if key == "btts_yes":
        return match.btts
    raise ValueError(f"unknown binary market key: {key}")


def run_backtest(
    fixtures: List[Dict], league_id: int = 0, season: int = 0, min_matches: int = 4
) -> BacktestReport:
    """Replay the season and score every model prediction against reality."""
    binary_pairs: Dict[str, List[Tuple[float, int]]] = {m: [] for m in _BINARY_MARKETS}
    result_rows: List[Tuple[Dict[str, float], str]] = []
    scored = 0

    for match in iter_scored_matches(fixtures, min_matches=min_matches):
        preds = predict_match(match)
        scored += 1

        for market, key in _BINARY_MARKETS.items():
            binary_pairs[market].append((preds[key], _outcome(match, key)))

        result_rows.append((
            {"1": preds["result_1"], "X": preds["result_X"], "2": preds["result_2"]},
            match.result,
        ))

    binary_results = [score_binary(m, binary_pairs[m]) for m in _BINARY_MARKETS]
    result_1x2 = score_multiclass("Match Result (1X2)", result_rows)

    return BacktestReport(
        league_id=league_id,
        season=season,
        min_matches=min_matches,
        total_matches_scored=scored,
        binary=binary_results,
        result_1x2=result_1x2,
    )
