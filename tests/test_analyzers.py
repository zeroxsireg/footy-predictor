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


def test_cards_corners_shots_are_disabled_by_default(high_scoring_home, high_scoring_away):
    for key in ("cards", "corners", "shots"):
        assert ANALYZER_REGISTRY[key] is None
    orchestrator = BettingOrchestrator()
    assert orchestrator.active_analyzers() == ["goals", "result"]
    analysis = orchestrator.analyze_match(high_scoring_home, high_scoring_away)
    assert not any(
        word in r.market for r in analysis.recommendations
        for word in ("Cards", "Corners", "Shots")
    )


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


# ── small-sample shrinkage (goals / 1X2 calibration) ──────────────────────────

def _stats(mp, wins, draws, losses, gf, ga, fts, cs, form):
    from core.models import Team, TeamStats
    return TeamStats(
        team=Team(id=1, name="T"), matches_played=mp, wins=wins, draws=draws, losses=losses,
        goals_for=gf, goals_against=ga, shots_total=0, shots_on_target=0, corners=0,
        yellow_cards=0, red_cards=0, form=form, clean_sheets=cs, failed_to_score=fts,
    )


def test_btts_never_certain_after_four_games():
    from analyzers.goals_analyzer import GoalsAnalyzer
    # 4 games, both sides always scored and never kept a clean sheet: old model gave 100%.
    team = _stats(4, 2, 1, 1, 8, 6, 0, 0, "WDLW")
    p = GoalsAnalyzer().btts_yes_probability(team, team)
    assert 0.5 < p <= 0.97
    assert p < 0.85   # shrunk toward the league average (old model: 100%)


def test_btts_sample_size_increases_confidence():
    from analyzers.goals_analyzer import GoalsAnalyzer
    small = _stats(4, 2, 1, 1, 8, 6, 0, 0, "WDLW")
    large = _stats(34, 17, 8, 9, 68, 51, 0, 0, "WDLWW")
    g = GoalsAnalyzer()
    assert g.btts_yes_probability(large, large) > g.btts_yes_probability(small, small)


def test_over_probabilities_clamped_with_tiny_sample():
    from analyzers.goals_analyzer import GoalsAnalyzer
    wild = _stats(1, 1, 0, 0, 9, 0, 0, 1, "W")
    probs = GoalsAnalyzer().match_goals_probabilities(wild, wild)
    assert all(0.03 <= v <= 0.97 for v in probs.values())
    assert probs["over_1_5"] < 0.97 or probs["over_1_5"] == pytest.approx(0.97)
    assert probs["over_2_5"] < 0.9   # 1 game of 9 goals must not dominate


def test_result_probabilities_shrunk_and_normalised_early_season():
    from analyzers.result_analyzer import ResultAnalyzer
    # Good start vs poor start over only 4 games: old model gave a 92% home win.
    strong = _stats(4, 3, 1, 0, 8, 3, 0, 1, "WWDW")
    weak = _stats(4, 0, 1, 3, 2, 7, 1, 0, "LLDL")
    probs = ResultAnalyzer().result_probabilities(strong, weak)
    assert sum(probs.values()) == pytest.approx(1.0)
    assert probs["1"] > probs["2"]
    assert probs["1"] <= 0.97
    assert probs["1"] < 0.80


def test_result_probabilities_clamp_holds_for_extreme_inputs():
    from analyzers.result_analyzer import ResultAnalyzer
    strong = _stats(38, 38, 0, 0, 200, 0, 0, 38, "WWWWW")
    weak = _stats(38, 0, 0, 38, 0, 200, 38, 0, "LLLLL")
    probs = ResultAnalyzer().result_probabilities(strong, weak)
    assert max(probs.values()) < 0.98 and min(probs.values()) > 0.02
    assert sum(probs.values()) == pytest.approx(1.0)


def test_clamp_probability_and_renormalisation_bounds():
    from analyzers.result_analyzer import ResultAnalyzer
    from core.shrinkage import clamp_probability
    assert clamp_probability(1.0) == 0.97 and clamp_probability(0.0) == 0.03
    out = ResultAnalyzer._clamp_and_renormalize({"1": 0.995, "X": 0.003, "2": 0.002})
    assert sum(out.values()) == pytest.approx(1.0)
    assert out["1"] < 0.97 and min(out.values()) >= 0.029
