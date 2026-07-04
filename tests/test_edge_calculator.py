"""
Tests for core.edge_calculator — the money math.

These are pure functions with known closed-form answers, so we assert exact
(approx) values rather than just "runs without error".
"""

import pytest

from core import edge_calculator as ec


# ── implied_probability ───────────────────────────────────────────────────────

def test_implied_probability_even_odds():
    assert ec.implied_probability(2.0) == pytest.approx(0.5)


def test_implied_probability_short_odds():
    assert ec.implied_probability(1.25) == pytest.approx(0.8)


@pytest.mark.parametrize("bad_odds", [1.0, 0.5, 0.0, -3.0])
def test_implied_probability_guards_invalid_odds(bad_odds):
    # Odds <= 1.0 make no sense as a payout; function returns certainty.
    assert ec.implied_probability(bad_odds) == 1.0


# ── calculate_edge ────────────────────────────────────────────────────────────

def test_edge_positive_when_we_beat_the_market():
    # We say 60%, market implies 50% -> +10% edge.
    assert ec.calculate_edge(0.60, 2.0) == pytest.approx(0.10)


def test_edge_negative_when_market_beats_us():
    assert ec.calculate_edge(0.40, 2.0) == pytest.approx(-0.10)


def test_edge_zero_at_fair_odds():
    assert ec.calculate_edge(0.50, 2.0) == pytest.approx(0.0)


# ── calculate_ev ──────────────────────────────────────────────────────────────

def test_ev_zero_at_fair_odds():
    assert ec.calculate_ev(0.50, 2.0) == pytest.approx(0.0)


def test_ev_positive_with_edge():
    # p=0.6, net odds=1.0 -> 0.6*1 - 0.4 = +0.20 -> +20%.
    assert ec.calculate_ev(0.60, 2.0) == pytest.approx(20.0)


def test_ev_negative_without_edge():
    assert ec.calculate_ev(0.40, 2.0) == pytest.approx(-20.0)


# ── calculate_kelly ───────────────────────────────────────────────────────────

def test_kelly_matches_closed_form():
    # f* = (b*p - q)/b, b=1, p=0.6, q=0.4 -> 0.2
    assert ec.calculate_kelly(0.60, 2.0) == pytest.approx(0.20)


def test_kelly_clamped_to_zero_when_no_edge():
    assert ec.calculate_kelly(0.40, 2.0) == 0.0


def test_kelly_zero_when_odds_offer_no_profit():
    # b <= 0 (odds 1.0) -> guard returns 0.0
    assert ec.calculate_kelly(0.99, 1.0) == 0.0


def test_kelly_scales_with_confidence():
    low = ec.calculate_kelly(0.55, 2.0)
    high = ec.calculate_kelly(0.75, 2.0)
    assert 0.0 < low < high


# ── extremize ─────────────────────────────────────────────────────────────────

def test_extremize_fixed_point_at_half():
    assert ec.extremize(0.50) == pytest.approx(0.50)


def test_extremize_pushes_away_from_half():
    # 0.5 + (0.8-0.5)*1.3 = 0.89
    assert ec.extremize(0.80, factor=1.3) == pytest.approx(0.89)
    # Below 0.5 gets pushed down.
    assert ec.extremize(0.20, factor=1.3) < 0.20


def test_extremize_clamped_to_bounds():
    assert ec.extremize(0.99, factor=2.0) == 0.99
    assert ec.extremize(0.01, factor=2.0) == 0.01


# ── evaluate_bet (the integration point) ──────────────────────────────────────

def test_evaluate_bet_returns_bet_verdict_on_strong_edge():
    decision = ec.evaluate_bet(our_probability_pct=72.0, decimal_odds=2.10)
    assert decision.verdict == "BET"
    assert decision.verdict_emoji == "✅"
    assert decision.edge > ec.MIN_EDGE_THRESHOLD
    assert decision.kelly_quarter == pytest.approx(decision.kelly_full * ec.KELLY_FRACTION, abs=1e-4)
    assert decision.kelly_quarter < decision.kelly_full  # quarter Kelly is smaller


def test_evaluate_bet_returns_value_verdict_on_thin_edge():
    # Edge just above 0 but below the 5% BET threshold.
    decision = ec.evaluate_bet(our_probability_pct=52.0, decimal_odds=2.0)
    assert decision.verdict == "VALUE"
    assert 0 < decision.edge < ec.MIN_EDGE_THRESHOLD


def test_evaluate_bet_returns_pass_verdict_without_edge():
    decision = ec.evaluate_bet(our_probability_pct=40.0, decimal_odds=2.0)
    assert decision.verdict == "PASS"
    assert decision.edge <= 0
    assert decision.kelly_quarter == 0.0


def test_evaluate_bet_respects_custom_min_edge():
    # With a huge threshold even a real edge is downgraded to VALUE.
    decision = ec.evaluate_bet(72.0, 2.10, min_edge=0.90)
    assert decision.verdict == "VALUE"


# ── Brier scoring ─────────────────────────────────────────────────────────────

def test_brier_score_perfect_and_worst():
    assert ec.brier_score(1.0, 1) == 0.0
    assert ec.brier_score(0.0, 1) == 1.0


def test_brier_score_partial():
    assert ec.brier_score(0.7, 1) == pytest.approx(0.09)


def test_brier_score_average_empty_is_zero():
    assert ec.brier_score_average([]) == 0.0


def test_brier_score_average_mean():
    preds = [(1.0, 1), (0.0, 1)]  # scores 0.0 and 1.0
    assert ec.brier_score_average(preds) == pytest.approx(0.5)


def test_brier_skill_score_relative_to_baseline():
    # our_brier 0.10 vs baseline 0.25 -> 1 - 0.4 = 0.6
    assert ec.brier_skill_score(0.10) == pytest.approx(0.6)
    # Equal to baseline -> 0 skill.
    assert ec.brier_skill_score(0.25) == pytest.approx(0.0)
    # Worse than baseline -> negative skill.
    assert ec.brier_skill_score(0.50) < 0


def test_brier_skill_score_guards_zero_baseline():
    assert ec.brier_skill_score(0.10, baseline_brier=0.0) == 0.0
