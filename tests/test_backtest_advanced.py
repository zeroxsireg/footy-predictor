"""Tests for the advanced time-decay 1X2 model and the RPS metric."""

import math

import pytest

from backtest.advanced import (
    WeightedTeam,
    WeightedLeague,
    AdvContext,
    iter_advanced_contexts,
    expected_goals,
    predict,
    _shrunk_strength,
)
from backtest.metrics import rps_1x2, rps_average, score_multiclass


def _fix(date, fid, hid, hn, aid, an, hg, ag, season, status="FT"):
    return {
        "fixture_id": fid, "date": date, "status": status, "season": season,
        "home_id": hid, "home_name": hn, "away_id": aid, "away_name": an,
        "home_goals": hg, "away_goals": ag,
    }


# ── weighted accumulators ─────────────────────────────────────────────────────

def test_weighted_team_accumulates():
    t = WeightedTeam()
    t.update(1.0, 2, 0)
    t.update(2.0, 1, 3)   # more recent -> higher weight
    assert t.matches == 2
    assert t.w == 3.0
    assert t.gf_w == pytest.approx(1.0 * 2 + 2.0 * 1)
    assert t.ga_w == pytest.approx(1.0 * 0 + 2.0 * 3)


def test_weighted_league_home_advantage():
    lg = WeightedLeague()
    lg.update(1.0, 2, 1)
    lg.update(1.0, 1, 0)
    assert lg.home_avg() == pytest.approx(1.5)
    assert lg.away_avg() == pytest.approx(0.5)
    assert lg.overall_avg() == pytest.approx(1.0)


# ── shrinkage ─────────────────────────────────────────────────────────────────

def test_shrinkage_pulls_thin_samples_to_league():
    # No observations -> strength collapses to 1.0 (league average).
    assert _shrunk_strength(0.0, 0.0, league_avg=1.4, k=5.0) == pytest.approx(1.0)


def test_shrinkage_keeps_signal_for_well_observed_team():
    # 20 weighted matches at 2.8 goals vs league 1.4 -> strong attack, ~2x, but
    # shrunk slightly toward 1.0.
    s = _shrunk_strength(goals_w=2.8 * 20, w=20, league_avg=1.4, k=5.0)
    assert 1.5 < s < 2.0


def test_shrinkage_respects_clamp():
    huge = _shrunk_strength(goals_w=50 * 30, w=30, league_avg=1.0, k=1.0)
    assert huge <= 3.0  # upper clamp


# ── expected goals / home advantage ───────────────────────────────────────────

def _ctx(home=(10, 20, 8), away=(10, 8, 15), lg=(1.35, 1.05)):
    hm, hgf, hga = home
    am, agf, aga = away
    return AdvContext(
        season=2024, date="2024-01-01T12:00:00Z", home_name="H", away_name="A",
        home_w=hm, home_gf_w=hgf, home_ga_w=hga,
        away_w=am, away_gf_w=agf, away_ga_w=aga,
        lg_overall_avg=(lg[0] + lg[1]) / 2, lg_home_avg=lg[0], lg_away_avg=lg[1],
        home_goals=0, away_goals=0,
    )


def test_home_advantage_lifts_home_lambda_for_equal_teams():
    # Identical team records -> home lambda should exceed away lambda purely from
    # the global home-advantage factor.
    ctx = _ctx(home=(10, 12, 12), away=(10, 12, 12), lg=(1.5, 1.0))
    lam_home, lam_away = expected_goals(ctx, k=5.0)
    assert lam_home > lam_away


def test_expected_goals_fallback_without_history():
    ctx = _ctx(home=(0, 0, 0), away=(0, 0, 0), lg=(1.5, 1.1))
    lam_home, lam_away = expected_goals(ctx, k=5.0)
    overall = (1.5 + 1.1) / 2
    # Strengths shrink to 1.0 -> lambdas are just the global home/away baselines.
    assert lam_home == pytest.approx(overall * (1.5 / overall))  # == 1.5
    assert lam_away == pytest.approx(overall * (1.1 / overall))  # == 1.1


def test_predict_returns_valid_1x2():
    p = predict(_ctx(), k=5.0)
    assert p["result_1"] + p["result_X"] + p["result_2"] == pytest.approx(1.0, abs=1e-6)
    assert all(0.0 <= v <= 1.0 for v in p.values())


# ── replay: no leakage, decay, season filter ─────────────────────────────────

def test_advanced_replay_no_leakage_and_decay():
    # Team A (id 1) plays 3 home games scoring 1,2,3; each snapshot must exclude
    # the current game, and later matches must carry more weight (decay).
    fixtures = [
        _fix("2024-01-01T12:00:00Z", 1, 1, "A", 2, "B", 1, 0, 2024),
        _fix("2024-01-08T12:00:00Z", 2, 1, "A", 3, "C", 2, 0, 2024),
        _fix("2024-01-15T12:00:00Z", 3, 1, "A", 4, "D", 3, 0, 2024),
    ]
    ctxs = list(iter_advanced_contexts(fixtures, xi=0.01))
    assert len(ctxs) == 3
    # Match 1: no prior history for A.
    assert ctxs[0].home_w == 0.0 and ctxs[0].home_gf_w == 0.0
    # Match 2: A has exactly one prior match (goals_for weighted > 0), current
    # match's 2 goals NOT included.
    assert ctxs[1].home_w > 0
    # Match 3: weighted goals reflect matches 1 and 2 only (1 and 2 goals).
    # With positive xi the more recent (2-goal) match weighs more than the older
    # (1-goal) one, so the weighted average goals-for exceeds the simple mean 1.5.
    weighted_avg = ctxs[2].home_gf_w / ctxs[2].home_w
    assert weighted_avg > 1.5


def test_advanced_replay_season_filter():
    fixtures = [
        _fix("2022-08-01T12:00:00Z", 1, 1, "A", 2, "B", 1, 0, 2022),
        _fix("2024-08-01T12:00:00Z", 2, 1, "A", 2, "B", 2, 1, 2024),
    ]
    scored = list(iter_advanced_contexts(fixtures, xi=0.0, score_seasons={2024}))
    assert len(scored) == 1
    assert scored[0].season == 2024
    # The 2022 match still built history for the 2024 snapshot.
    assert scored[0].home_w > 0


# ── RPS metric ────────────────────────────────────────────────────────────────

def test_rps_perfect_is_zero():
    assert rps_1x2({"1": 1.0, "X": 0.0, "2": 0.0}, "1") == 0.0


def test_rps_penalises_ordinal_distance():
    # Confidently predicting home(1) ...
    wrong_by_two = rps_1x2({"1": 1.0, "X": 0.0, "2": 0.0}, "2")   # actual away
    wrong_by_one = rps_1x2({"1": 1.0, "X": 0.0, "2": 0.0}, "X")   # actual draw
    assert wrong_by_two == pytest.approx(1.0)
    assert wrong_by_one == pytest.approx(0.5)
    assert wrong_by_two > wrong_by_one


def test_rps_average_and_multiclass_field():
    rows = [({"1": 1.0, "X": 0.0, "2": 0.0}, "1"), ({"1": 0.0, "X": 0.0, "2": 1.0}, "2")]
    assert rps_average(rows) == 0.0
    assert score_multiclass("1X2", rows).rps == 0.0
