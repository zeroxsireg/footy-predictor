"""
Tests for the market analyzers.

Covers the shared BaseAnalyzer helpers (Poisson, confidence buckets) and the
GoalsAnalyzer end-to-end against high- and low-scoring scenarios.
"""

import math

import pytest

from analyzers.base import BaseAnalyzer
from analyzers.goals_analyzer import GoalsAnalyzer
from analyzers import ANALYZER_REGISTRY
from betting.orchestrator import BettingOrchestrator
from core.betting_models import BettingRecommendation


# ── BaseAnalyzer helpers ──────────────────────────────────────────────────────

def test_poisson_matches_manual_computation():
    # P(X > 2.5 | lambda=4) = 1 - P(0) - P(1) - P(2)
    lam = 4.0
    manual = 1.0 - sum(lam**k * math.exp(-lam) / math.factorial(k) for k in range(3))
    assert BaseAnalyzer._poisson_over_prob(lam, 2.5) == pytest.approx(manual)


def test_poisson_zero_lambda_is_zero():
    assert BaseAnalyzer._poisson_over_prob(0.0, 1.5) == 0.0


def test_poisson_bounded_between_zero_and_one():
    for lam in (0.1, 1.0, 3.5, 8.0, 20.0):
        p = BaseAnalyzer._poisson_over_prob(lam, 2.5)
        assert 0.0 <= p <= 1.0


def test_poisson_monotonic_in_lambda():
    # More expected goals -> higher P(over 2.5).
    low = BaseAnalyzer._poisson_over_prob(1.0, 2.5)
    high = BaseAnalyzer._poisson_over_prob(4.0, 2.5)
    assert high > low


class _Dummy(BaseAnalyzer):
    def get_required_stats(self):
        return []

    def analyze(self, home_stats, away_stats, **kwargs):
        return []


@pytest.mark.parametrize(
    "prob,expected",
    [
        (90.0, "HIGH"),
        (55.0, "HIGH"),   # boundary is inclusive
        (54.9, "MEDIUM"),
        (40.0, "MEDIUM"),  # boundary is inclusive
        (39.9, "LOW"),
        (0.0, "LOW"),
    ],
)
def test_confidence_buckets(prob, expected):
    assert _Dummy()._get_confidence_level(prob) == expected


# ── GoalsAnalyzer scenarios ───────────────────────────────────────────────────

def _selections(recs, market):
    return {r.selection for r in recs if r.market == market}


def test_goals_analyzer_returns_recommendations(high_scoring_home, high_scoring_away):
    recs = GoalsAnalyzer().analyze(high_scoring_home, high_scoring_away)
    assert recs, "expected at least one recommendation for a high-scoring match"
    assert all(isinstance(r, BettingRecommendation) for r in recs)
    assert all(0.0 <= r.percentage <= 100.0 for r in recs)


def test_high_scoring_match_recommends_over(high_scoring_home, high_scoring_away):
    recs = GoalsAnalyzer().analyze(high_scoring_home, high_scoring_away)
    match_goals = _selections(recs, "Match Goals")
    assert any("Over" in sel for sel in match_goals)
    assert "Under 2.5" not in match_goals


def test_low_scoring_match_recommends_under(low_scoring_home, low_scoring_away):
    recs = GoalsAnalyzer().analyze(low_scoring_home, low_scoring_away)
    match_goals = _selections(recs, "Match Goals")
    assert any("Under" in sel for sel in match_goals)
    assert "Over 2.5" not in match_goals


def test_match_goals_capped_at_two_picks(high_scoring_home, high_scoring_away):
    recs = GoalsAnalyzer().analyze(high_scoring_home, high_scoring_away)
    match_goals = [r for r in recs if r.market == "Match Goals"]
    assert len(match_goals) <= 2


def test_odds_range_is_deprecated_and_none(high_scoring_home, high_scoring_away):
    recs = GoalsAnalyzer().analyze(high_scoring_home, high_scoring_away)
    assert all(r.odds_range is None for r in recs)


# ── Orchestrator wiring ───────────────────────────────────────────────────────

def test_registry_is_populated():
    assert ANALYZER_REGISTRY, "ANALYZER_REGISTRY should not be empty"


def test_orchestrator_runs_all_analyzers(high_scoring_home, high_scoring_away):
    orchestrator = BettingOrchestrator()
    analysis = orchestrator.analyze_match(high_scoring_home, high_scoring_away)

    assert analysis.match_info == "Attackers United vs Goal Machine"
    assert isinstance(analysis.recommendations, list)
    summary = analysis.summary
    assert summary["total_recommendations"] == len(analysis.recommendations)
    assert (
        summary["high_confidence"]
        + summary["medium_confidence"]
        + summary["low_confidence"]
        == len(analysis.recommendations)
    )


def test_orchestrator_subset_enables_only_requested_market(high_scoring_home, high_scoring_away):
    orchestrator = BettingOrchestrator(enabled={"goals": GoalsAnalyzer})
    assert orchestrator.active_analyzers() == ["goals"]
    analysis = orchestrator.analyze_match(high_scoring_home, high_scoring_away)
    markets = {r.market for r in analysis.recommendations}
    # Only goals-related markets should appear.
    assert all(
        "Goals" in m or "Both Teams to Score" in m for m in markets
    ), markets


def test_orchestrator_isolates_a_failing_analyzer(high_scoring_home, high_scoring_away):
    class Exploding(BaseAnalyzer):
        def get_required_stats(self):
            return []

        def analyze(self, home_stats, away_stats, **kwargs):
            raise RuntimeError("boom")

    orchestrator = BettingOrchestrator(enabled={"goals": GoalsAnalyzer, "boom": Exploding})
    # Should not raise; the failing analyzer is swallowed, goals still produce output.
    analysis = orchestrator.analyze_match(high_scoring_home, high_scoring_away)
    assert isinstance(analysis.recommendations, list)
