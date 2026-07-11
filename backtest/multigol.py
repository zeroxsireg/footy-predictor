"""
Multigol backtest.

Multigol markets (goals within a range: total, home, away) come for free from
the xG model's score matrix — no extra data. Here we score them the same way as
every other market, to confirm they're calibrated.
"""

from typing import Dict, List, Tuple

from backtest.xg_compare import iter_xg_predictions
from backtest.metrics import BinaryMarketResult, score_binary

# (display name, probability key, dimension, low, high)
MULTIGOL_LINES: List[Tuple[str, str, str, int, int]] = [
    ("Multigol 1-2", "mg_total_1_2", "total", 1, 2),
    ("Multigol 2-3", "mg_total_2_3", "total", 2, 3),
    ("Multigol 1-3", "mg_total_1_3", "total", 1, 3),
    ("Multigol 2-4", "mg_total_2_4", "total", 2, 4),
    ("MG Casa 1-2", "mg_home_1_2", "home", 1, 2),
    ("MG Casa 1-3", "mg_home_1_3", "home", 1, 3),
    ("MG Trasferta 1-2", "mg_away_1_2", "away", 1, 2),
    ("MG Trasferta 1-3", "mg_away_1_3", "away", 1, 3),
]


def multigol_outcome(home_goals: int, away_goals: int, dim: str, lo: int, hi: int) -> int:
    value = home_goals + away_goals if dim == "total" else home_goals if dim == "home" else away_goals
    return 1 if lo <= value <= hi else 0


def run_multigol_backtest(
    fixtures: List[Dict], xg_map: Dict[str, Dict], *,
    target_season: int | None = None, xi: float = 0.0, k: float = 5.0,
    min_matches: int = 4,
) -> Tuple[int, List[BinaryMarketResult]]:
    """Score every multigol line on the target season using the xG model."""
    pairs = {name: [] for name, *_ in MULTIGOL_LINES}
    n = 0
    for pred in iter_xg_predictions(
        fixtures, xg_map, target_season=target_season, xi=xi, k=k, min_matches=min_matches
    ):
        hg, ag = pred["home_goals"], pred["away_goals"]
        probs = pred["probs"]
        n += 1
        for name, key, dim, lo, hi in MULTIGOL_LINES:
            pairs[name].append((probs[key], multigol_outcome(hg, ag, dim, lo, hi)))
    return n, [score_binary(name, pairs[name]) for name, *_ in MULTIGOL_LINES]
