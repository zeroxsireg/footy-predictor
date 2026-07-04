"""
Scoring metrics for the backtest.

- Brier score: mean squared error of probabilistic forecasts (0 = perfect,
  0.25 = a coin flip at 50%). Reuses core.edge_calculator so the definition
  matches the live app.
- Hit-rate: how often the model's call (>=50% -> "yes", or argmax for 1X2)
  was correct.
- Calibration: when the model says 70%, does it happen ~70% of the time?
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from core.edge_calculator import brier_score_average, brier_skill_score


@dataclass
class BinaryMarketResult:
    """Scoring for a yes/no market (e.g. Over 2.5, BTTS)."""
    market: str
    n: int
    brier: float
    brier_skill: float          # vs a naive "always predict the base rate" forecaster
    hit_rate: float             # accuracy of the >=50% call
    avg_prediction: float       # mean predicted P(yes)
    base_rate: float            # actual frequency of "yes"
    calibration: List[Tuple[str, int, float, float]] = field(default_factory=list)
    # each row: (bucket_label, count, avg_predicted, actual_frequency)


@dataclass
class MulticlassMarketResult:
    """Scoring for the 1X2 market."""
    market: str
    n: int
    brier: float                # multiclass Brier (sum over classes, averaged)
    hit_rate: float             # argmax prediction == actual outcome
    per_class_base_rate: Dict[str, float]


def score_binary(market: str, pairs: List[Tuple[float, int]], n_bins: int = 10) -> BinaryMarketResult:
    """Score a list of (predicted_probability, actual_outcome 0/1) pairs."""
    n = len(pairs)
    if n == 0:
        return BinaryMarketResult(market, 0, 0.0, 0.0, 0.0, 0.0, 0.0)

    base_rate = sum(o for _, o in pairs) / n
    avg_pred = sum(p for p, _ in pairs) / n
    brier = brier_score_average(pairs)

    # Baseline: always forecast the base rate -> Brier = p*(1-p).
    baseline = base_rate * (1 - base_rate)
    skill = brier_skill_score(brier, baseline) if baseline > 0 else 0.0

    hits = sum(1 for p, o in pairs if (p >= 0.5) == (o == 1))
    hit_rate = hits / n

    calibration = _calibration_bins(pairs, n_bins)
    return BinaryMarketResult(
        market=market, n=n, brier=round(brier, 4), brier_skill=round(skill, 4),
        hit_rate=round(hit_rate, 4), avg_prediction=round(avg_pred, 4),
        base_rate=round(base_rate, 4), calibration=calibration,
    )


def _calibration_bins(
    pairs: List[Tuple[float, int]], n_bins: int
) -> List[Tuple[str, int, float, float]]:
    """Group predictions into probability buckets and compare predicted vs actual."""
    buckets: List[List[Tuple[float, int]]] = [[] for _ in range(n_bins)]
    for p, o in pairs:
        idx = min(int(p * n_bins), n_bins - 1)
        buckets[idx].append((p, o))

    rows = []
    for i, bucket in enumerate(buckets):
        if not bucket:
            continue
        lo, hi = i / n_bins, (i + 1) / n_bins
        count = len(bucket)
        avg_pred = sum(p for p, _ in bucket) / count
        actual = sum(o for _, o in bucket) / count
        rows.append((f"{lo:.0%}-{hi:.0%}", count, round(avg_pred, 4), round(actual, 4)))
    return rows


def score_multiclass(
    market: str, rows: List[Tuple[Dict[str, float], str]]
) -> MulticlassMarketResult:
    """
    Score 1X2 predictions.

    rows: list of ({"1":p1,"X":pX,"2":p2}, actual_class) tuples.
    """
    n = len(rows)
    classes = ("1", "X", "2")
    if n == 0:
        return MulticlassMarketResult(market, 0, 0.0, 0.0, {c: 0.0 for c in classes})

    brier_sum = 0.0
    hits = 0
    class_counts = {c: 0 for c in classes}
    for probs, actual in rows:
        brier_sum += sum((probs.get(c, 0.0) - (1.0 if c == actual else 0.0)) ** 2 for c in classes)
        predicted = max(classes, key=lambda c: probs.get(c, 0.0))
        if predicted == actual:
            hits += 1
        class_counts[actual] += 1

    return MulticlassMarketResult(
        market=market,
        n=n,
        brier=round(brier_sum / n, 4),
        hit_rate=round(hits / n, 4),
        per_class_base_rate={c: round(class_counts[c] / n, 4) for c in classes},
    )
