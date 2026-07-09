"""Tests for the Glicko-2 football model and the ensemble evaluator."""

import pytest

from backtest import glicko
from backtest.glicko import GlickoRating, updated, predict_1x2, mov_multiplier
from backtest.ensemble import run_ensemble_eval, _blend


# ── rating updates ────────────────────────────────────────────────────────────

def test_winning_raises_rating_losing_lowers():
    base = GlickoRating()
    opp = GlickoRating()
    after_win = updated(base, opp, score=1.0)
    after_loss = updated(base, opp, score=0.0)
    assert after_win.r > base.r
    assert after_loss.r < base.r


def test_rating_deviation_shrinks_with_a_game():
    base = GlickoRating()   # RD 350 (very uncertain)
    after = updated(base, GlickoRating(), score=1.0)
    assert after.rd < base.rd   # a played match reduces uncertainty


def test_draw_moves_rating_toward_opponent():
    strong = GlickoRating(r=1700, rd=80)
    weak = GlickoRating(r=1300, rd=80)
    # A draw is a bad result for the strong side -> its rating drops a bit.
    after = updated(strong, weak, score=0.5)
    assert after.r < strong.r


def test_mov_multiplier_bigger_for_larger_margins():
    assert mov_multiplier(0) == pytest.approx(1.0)
    assert mov_multiplier(1) == pytest.approx(1.0)
    assert mov_multiplier(4) > mov_multiplier(2) > mov_multiplier(1)


def test_mov_amplifies_rating_change():
    base, opp = GlickoRating(), GlickoRating()
    small = updated(base, opp, score=1.0, mov=1.0)
    big = updated(base, opp, score=1.0, mov=mov_multiplier(5))
    assert big.r > small.r   # a thrashing moves the rating more


# ── predictions ───────────────────────────────────────────────────────────────

def test_predict_1x2_is_a_distribution():
    p = predict_1x2(GlickoRating(), GlickoRating())
    assert p["result_1"] + p["result_X"] + p["result_2"] == pytest.approx(1.0, abs=1e-6)
    assert all(0.0 <= v <= 1.0 for v in p.values())


def test_home_advantage_favours_home_for_equal_teams():
    p = predict_1x2(GlickoRating(), GlickoRating(), home_adv=80.0)
    assert p["result_1"] > p["result_2"]   # equal ratings, but home edge


def test_stronger_team_more_likely_to_win():
    strong_home = predict_1x2(GlickoRating(r=1800), GlickoRating(r=1300))
    assert strong_home["result_1"] > strong_home["result_2"]


def test_blend_averages_two_forecasts():
    a = {"1": 0.6, "X": 0.3, "2": 0.1}
    b = {"1": 0.4, "X": 0.3, "2": 0.3}
    blended = _blend(a, b)
    assert blended == {"1": 0.5, "X": 0.3, "2": pytest.approx(0.2)}


# ── ensemble evaluator ────────────────────────────────────────────────────────

def _mini_season(season, n_rounds=6):
    teams = [(1, "A"), (2, "B"), (3, "C"), (4, "D")]
    scores = [(2, 0), (1, 1), (0, 2), (3, 1), (1, 0), (2, 2)]
    fixtures, fid, day, si = [], 1, 1, 0
    for _ in range(n_rounds):
        for i in range(len(teams)):
            for j in range(len(teams)):
                if i == j:
                    continue
                hg, ag = scores[si % len(scores)]
                si += 1
                fixtures.append({
                    "fixture_id": fid, "date": f"{season}-0{1+day//28}-{1+day%28:02d}T12:00:00Z",
                    "status": "FT", "season": season,
                    "home_id": teams[i][0], "home_name": teams[i][1],
                    "away_id": teams[j][0], "away_name": teams[j][1],
                    "home_goals": hg, "away_goals": ag,
                })
                fid += 1
                day += 1
    return fixtures


def test_ensemble_eval_scores_three_models():
    fixtures = _mini_season(2023) + _mini_season(2024)
    results = run_ensemble_eval(fixtures, target_season=2024, xi=0.002, k=5.0)
    labels = {r.label for r in results}
    assert labels == {"Poisson forze", "Glicko-2", "Ensemble"}
    for r in results:
        assert r.scored.n > 0
        assert 0.0 <= r.scored.rps <= 2.0
        assert 0.0 <= r.scored.hit_rate <= 1.0
