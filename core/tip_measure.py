"""
Offline, point-in-time, out-of-sample measurement of every tip market (feeds
core/tip_reliability.py). Read-only on backtest/data, no network.

The production configuration (xG-Poisson, xi=0, k=2) is replayed with
backtest.xg_compare.iter_xg_predictions; only the scoring function is wrapped to keep the
joint matrix, so each market probability is summed from that same matrix.
"""

import statistics as st
from typing import Dict, Iterable, List, Sequence, Tuple

import backtest.xg_compare as xc
from backtest.advanced import expected_goals
from backtest.models import _markets_from_matrix, _score_matrix
from backtest.xg_data import load_xg_map, xg_cache_path
from core.contracts import TIP_CATALOG
from core.predictor import K_SHRINK, XI
from core.tip_defs import TIP_PREDICATES, tip_probability

# (league, target season, history seasons): Serie A 2024/2025, Premier 2024/2025, Liga 2025.
CASES = [(135, 2024, [2023]), (39, 2024, [2023]), (135, 2025, [2023, 2024]),
         (39, 2025, [2023, 2024]), (140, 2025, [2023, 2024])]
BANDS = (0.60, 0.75, 0.85)


def collect(cases: Sequence[Tuple[int, int, List[int]]] = CASES) -> List[dict]:
    """Rows {matrix, home_goals, away_goals, probs} for every scored target-season match."""
    from backtest.ablation import load_seasons

    def capture(ctx, k: float = 5.0, rho: float = 0.0):
        lam_h, lam_a = expected_goals(ctx, k=k)
        matrix = _score_matrix(lam_h, lam_a, rho=0.0)
        out = _markets_from_matrix(matrix)
        out["matrix"] = matrix
        return out

    rows: List[dict] = []
    original = xc.strength_predict
    xc.strength_predict = capture
    try:
        for league, season, hist in cases:
            fixtures = load_seasons(league, hist + [season])
            xg: Dict = {}
            for y in hist + [season]:
                xg.update(load_xg_map(xg_cache_path(league, y)))
            for r in xc.iter_xg_predictions(
                    fixtures, xg, target_season=season, xi=XI, k=K_SHRINK):
                rows.append(dict(r, matrix=r["probs"]["matrix"]))
    finally:
        xc.strength_predict = original
    return rows


def _stats(pairs: List[Tuple[float, int]]) -> dict:
    y = [b for _, b in pairs]
    freq = sum(y) / len(y)
    brier = st.mean((a - b) ** 2 for a, b in pairs)
    ref = st.mean((freq - b) ** 2 for b in y)
    out = {"n": len(pairs), "freq": freq, "p_mean": st.mean(a for a, _ in pairs),
           "skill": (1 - brier / ref) if ref > 0 else 0.0, "bands": {}}
    for th in BANDS:
        sel = [(a, b) for a, b in pairs if a >= th]
        out["bands"][th] = ({"n": len(sel), "pred": st.mean(a for a, _ in sel),
                             "real": st.mean(b for _, b in sel)} if sel else None)
    return out


def measure(rows: Iterable[dict]) -> Dict[str, dict]:
    """key -> stats for every TIP_CATALOG key; '@family' -> pooled stats of that family."""
    rows = list(rows)
    per_key: Dict[str, List[Tuple[float, int]]] = {}
    for key in TIP_CATALOG:
        pred = TIP_PREDICATES[key]
        per_key[key] = [(tip_probability(r["matrix"], key),
                         1 if pred(r["home_goals"], r["away_goals"]) else 0) for r in rows]
    result = {key: _stats(pairs) for key, pairs in per_key.items()}
    fam: Dict[str, List[Tuple[float, int]]] = {}
    for key, pairs in per_key.items():
        fam.setdefault(TIP_CATALOG[key][1], []).extend(pairs)
    result.update({f"@{f}": _stats(p) for f, p in fam.items()})
    return result
