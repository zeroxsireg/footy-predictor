"""Tests for the backtest scoring metrics (Brier, calibration, 1X2)."""

from backtest.metrics import score_binary, score_multiclass


def test_perfect_binary_predictions_score_zero_brier():
    pairs = [(1.0, 1), (0.0, 0), (1.0, 1), (0.0, 0)]
    r = score_binary("Perfect", pairs)
    assert r.n == 4
    assert r.brier == 0.0
    assert r.hit_rate == 1.0
    assert r.base_rate == 0.5


def test_coin_flip_binary_brier_is_a_quarter():
    # Always predict 50% on a fair outcome -> Brier ~ 0.25.
    pairs = [(0.5, 1), (0.5, 0), (0.5, 1), (0.5, 0)]
    r = score_binary("Coin", pairs)
    assert r.brier == 0.25
    assert r.avg_prediction == 0.5


def test_binary_hit_rate_counts_the_call():
    # 0.8 -> "yes" call. Correct when outcome==1.
    pairs = [(0.8, 1), (0.8, 0), (0.2, 0), (0.2, 1)]
    r = score_binary("Calls", pairs)
    assert r.hit_rate == 0.5  # 2 of 4 calls correct


def test_calibration_bins_partition_all_samples():
    pairs = [(0.05, 0), (0.15, 0), (0.55, 1), (0.95, 1), (0.95, 1)]
    r = score_binary("Bins", pairs, n_bins=10)
    total = sum(count for _, count, _, _ in r.calibration)
    assert total == len(pairs)
    # The 90-100% bucket holds the two 0.95 predictions, both hit -> actual 100%.
    top = [row for row in r.calibration if row[0] == "90%-100%"]
    assert top and top[0][1] == 2 and top[0][3] == 1.0


def test_empty_binary_is_safe():
    r = score_binary("Empty", [])
    assert r.n == 0 and r.brier == 0.0


def test_multiclass_perfect_predictions():
    rows = [
        ({"1": 1.0, "X": 0.0, "2": 0.0}, "1"),
        ({"1": 0.0, "X": 1.0, "2": 0.0}, "X"),
        ({"1": 0.0, "X": 0.0, "2": 1.0}, "2"),
    ]
    r = score_multiclass("1X2", rows)
    assert r.n == 3
    assert r.brier == 0.0
    assert r.hit_rate == 1.0
    assert r.per_class_base_rate == {"1": round(1/3, 4), "X": round(1/3, 4), "2": round(1/3, 4)}


def test_multiclass_argmax_hit_rate():
    rows = [
        ({"1": 0.5, "X": 0.3, "2": 0.2}, "1"),  # argmax 1 == actual -> hit
        ({"1": 0.5, "X": 0.3, "2": 0.2}, "2"),  # argmax 1 != actual -> miss
    ]
    r = score_multiclass("1X2", rows)
    assert r.hit_rate == 0.5
