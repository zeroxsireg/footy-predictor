"""Tests for the comparison models (Poisson strength & Dixon-Coles)."""

import pytest

from core.models import Team, TeamStats
from backtest.engine import MatchContext, ScoredMatch
from backtest import models as M


def _ctx(lam_setup="balanced", home_goals=1, away_goals=1) -> MatchContext:
    """
    Build a MatchContext with controllable home/away split records.
    'balanced' -> both teams league-average; 'home_strong' -> home scores a lot.
    """
    def stats(name):
        return TeamStats(
            team=Team(id=0, name=name), matches_played=10, wins=4, draws=3, losses=3,
            goals_for=14, goals_against=12, shots_total=0, shots_on_target=0,
            corners=0, yellow_cards=0, red_cards=0, form="WWDLD",
            clean_sheets=3, failed_to_score=2,
        )

    if lam_setup == "home_strong":
        home_home = (5, 15, 2)   # 3.0 scored, 0.4 conceded at home
        away_away = (5, 3, 10)   # 0.6 scored, 2.0 conceded away
    else:
        home_home = (5, 7, 5)    # ~league average
        away_away = (5, 5, 6)

    return MatchContext(
        scored=ScoredMatch("2025-01-01", "H", "A", stats("H"), stats("A"), home_goals, away_goals),
        lg_home_avg=1.5, lg_away_avg=1.1,
        home_home=home_home, away_away=away_away,
    )


# ── score matrix / markets ────────────────────────────────────────────────────

def test_score_matrix_is_a_probability_distribution():
    matrix = M._score_matrix(1.5, 1.1, rho=0.0)
    total = sum(sum(row) for row in matrix)
    assert total == pytest.approx(1.0, abs=1e-6)


def test_dixon_coles_matrix_still_normalised():
    matrix = M._score_matrix(1.5, 1.1, rho=M.DC_RHO)
    total = sum(sum(row) for row in matrix)
    assert total == pytest.approx(1.0, abs=1e-6)


def test_dc_only_changes_low_score_cells():
    indep = M._score_matrix(1.4, 1.2, rho=0.0)
    dc = M._score_matrix(1.4, 1.2, rho=M.DC_RHO)
    # Cells outside {0,1}x{0,1} are unchanged relative to each other (both come
    # from the same pmf, only renormalised) -> ratio to a high cell is stable.
    # Simply assert the four low cells actually moved.
    changed = [(i, j) for i in (0, 1) for j in (0, 1) if abs(dc[i][j] - indep[i][j]) > 1e-6]
    assert len(changed) == 4


def test_markets_from_matrix_are_coherent():
    probs = M._markets_from_matrix(M._score_matrix(1.6, 1.3))
    # Over thresholds must be monotonically decreasing.
    assert probs["over_1_5"] >= probs["over_2_5"] >= probs["over_3_5"]
    # 1X2 sums to 1.
    assert probs["result_1"] + probs["result_X"] + probs["result_2"] == pytest.approx(1.0, abs=1e-6)
    # All probabilities in range.
    for v in probs.values():
        assert 0.0 <= v <= 1.0


def test_over_2_5_matches_manual_independent_poisson():
    import math
    lam, mu = 1.5, 1.2
    # P(total <= 2) manually for independent Poisson.
    def pois(k, l): return l**k * math.exp(-l) / math.factorial(k)
    p_le2 = 0.0
    for i in range(11):
        for j in range(11):
            if i + j <= 2:
                p_le2 += pois(i, lam) * pois(j, mu)
    expected_over = 1 - p_le2
    got = M._markets_from_matrix(M._score_matrix(lam, mu))["over_2_5"]
    assert got == pytest.approx(expected_over, abs=1e-3)


# ── expected goals / strength ─────────────────────────────────────────────────

def test_expected_goals_reflect_strength():
    balanced = M._expected_goals(_ctx("balanced"))
    strong = M._expected_goals(_ctx("home_strong"))
    # A strong home attack vs weak away defence -> more home goals expected.
    assert strong[0] > balanced[0]
    # Weak away attack vs strong home defence -> fewer away goals expected.
    assert strong[1] < balanced[1]


def test_expected_goals_fallback_when_no_split_history():
    ctx = MatchContext(
        scored=_ctx().scored, lg_home_avg=1.5, lg_away_avg=1.1,
        home_home=(0, 0, 0), away_away=(0, 0, 0),   # no games played yet
    )
    lam_home, lam_away = M._expected_goals(ctx)
    # Falls back to league baselines (strength ratios = 1).
    assert lam_home == pytest.approx(1.5, abs=1e-6)
    assert lam_away == pytest.approx(1.1, abs=1e-6)


# ── model wiring ──────────────────────────────────────────────────────────────

def test_all_models_return_the_core_markets():
    ctx = _ctx("home_strong")
    keys = {"over_1_5", "over_2_5", "over_3_5", "btts_yes", "result_1", "result_X", "result_2"}
    for model in (M.baseline_model, M.poisson_strength_model, M.dixon_coles_model):
        out = model(ctx)
        assert keys <= set(out)   # core markets present (strength models add multigol)
        assert all(0.0 <= v <= 1.0 for v in out.values())


def test_registry_lists_three_models():
    assert list(M.MODELS) == ["Baseline (attuale)", "Poisson forze", "Dixon-Coles"]
