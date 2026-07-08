"""
Ablation study for the advanced 1X2 model.

Answers, with numbers, "which of the research's techniques actually helps?":
scores the same target-season matches under different configurations
(single- vs multi-season history, time-decay strength xi, shrinkage k) and
reports RPS (primary), multiclass Brier and accuracy.

Same scored match set across every config -> a fair, apples-to-apples table.
"""

from dataclasses import dataclass
from typing import Dict, List

from backtest.data import cache_path, load_fixtures
from backtest.advanced import iter_advanced_contexts, predict
from backtest.metrics import score_multiclass


def load_seasons(league_id: int, seasons: List[int]) -> List[Dict]:
    """Load and tag several cached seasons into one fixture list."""
    out: List[Dict] = []
    for s in seasons:
        for rec in load_fixtures(cache_path(league_id, s)):
            rec = dict(rec)
            rec["season"] = s
            out.append(rec)
    return out


@dataclass
class Config:
    label: str
    seasons: List[int]      # which seasons to load as history+target
    xi: float               # time-decay per day (0 = no decay)
    k: float                # shrinkage pseudo-matches (0 = none)


@dataclass
class EvalResult:
    label: str
    n: int
    rps: float
    brier: float
    accuracy: float


def evaluate(
    fixtures: List[Dict], target_season: int, xi: float, k: float
) -> EvalResult:
    """Evaluate the advanced model's 1X2 predictions on the target season."""
    rows = []
    for ctx in iter_advanced_contexts(fixtures, xi=xi, score_seasons={target_season}):
        p = predict(ctx, k=k)
        rows.append((
            {"1": p["result_1"], "X": p["result_X"], "2": p["result_2"]},
            ctx.result,
        ))
    scored = score_multiclass("1X2", rows)
    return EvalResult(
        label="", n=scored.n, rps=scored.rps, brier=scored.brier,
        accuracy=scored.hit_rate,
    )


def run_ablation(
    league_id: int,
    target_season: int,
    history_seasons: List[int],
    xi_grid: List[float],
    k: float = 5.0,
) -> List[EvalResult]:
    """
    Build the ablation table. Every config scores the SAME target-season matches.
    """
    target_only = load_seasons(league_id, [target_season])
    multi = load_seasons(league_id, history_seasons + [target_season])

    results: List[EvalResult] = []

    # Reference: single season, no decay, no shrinkage — closest to old behaviour.
    r = evaluate(target_only, target_season, xi=0.0, k=0.0)
    r.label = "Solo stagione · no decay · no shrink"
    results.append(r)

    # Single season + shrinkage (isolates shrinkage alone).
    r = evaluate(target_only, target_season, xi=0.0, k=k)
    r.label = f"Solo stagione · no decay · shrink k={k:g}"
    results.append(r)

    # Multi-season, no decay (isolates the value of more history).
    r = evaluate(multi, target_season, xi=0.0, k=k)
    r.label = f"Multi-stagione · no decay · shrink k={k:g}"
    results.append(r)

    # Multi-season + time-decay sweep (isolates xi).
    for xi in xi_grid:
        r = evaluate(multi, target_season, xi=xi, k=k)
        r.label = f"Multi-stagione · decay ξ={xi:g}/g · shrink k={k:g}"
        results.append(r)

    return results
