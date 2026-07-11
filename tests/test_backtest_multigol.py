"""Tests for multigol probabilities and backtest."""

import pytest

from backtest.models import _score_matrix, _markets_from_matrix
from backtest.multigol import multigol_outcome, run_multigol_backtest, MULTIGOL_LINES


def test_multigol_keys_present_and_in_range():
    probs = _markets_from_matrix(_score_matrix(1.5, 1.2))
    for _, key, *_ in MULTIGOL_LINES:
        assert key in probs
        assert 0.0 <= probs[key] <= 1.0


def test_multigol_ranges_are_consistent():
    probs = _markets_from_matrix(_score_matrix(1.6, 1.3))
    # 1-3 contains 2-3, so it must be at least as likely.
    assert probs["mg_total_1_3"] >= probs["mg_total_2_3"]
    # 1-3 (home) contains 1-2 (home).
    assert probs["mg_home_1_3"] >= probs["mg_home_1_2"]


def test_multigol_total_matches_manual():
    matrix = _score_matrix(1.4, 1.1)
    manual = sum(
        matrix[i][j] for i in range(len(matrix)) for j in range(len(matrix))
        if 1 <= i + j <= 2
    )
    assert _markets_from_matrix(matrix)["mg_total_1_2"] == pytest.approx(manual, abs=1e-9)


def test_multigol_outcome():
    assert multigol_outcome(1, 1, "total", 1, 2) == 1   # total 2
    assert multigol_outcome(2, 1, "total", 1, 2) == 0   # total 3
    assert multigol_outcome(2, 0, "home", 1, 2) == 1
    assert multigol_outcome(0, 3, "away", 1, 3) == 1
    assert multigol_outcome(0, 0, "home", 1, 2) == 0


def _season(year, xg_bias=0.2):
    teams = [(1, "A"), (2, "B"), (3, "C"), (4, "D")]
    scores = [(2, 1), (0, 0), (3, 1), (1, 1), (2, 0), (1, 2)]
    fixtures, xg, fid, day, si = [], {}, year * 100, 1, 0
    for _ in range(5):
        for i in range(len(teams)):
            for j in range(len(teams)):
                if i == j:
                    continue
                hg, ag = scores[si % len(scores)]
                si += 1
                fixtures.append({
                    "fixture_id": fid, "date": f"{year}-0{1+day//28}-{1+day%28:02d}T12:00:00Z",
                    "status": "FT", "season": year,
                    "home_id": teams[i][0], "home_name": teams[i][1],
                    "away_id": teams[j][0], "away_name": teams[j][1],
                    "home_goals": hg, "away_goals": ag,
                })
                xg[str(fid)] = {"home_xg": hg + xg_bias, "away_xg": ag + xg_bias}
                fid += 1
                day += 1
    return fixtures, xg


def test_multigol_backtest_runs():
    fx, xg = _season(2024)
    n, results = run_multigol_backtest(fx, xg, target_season=2024, min_matches=2)
    assert n > 0
    assert len(results) == len(MULTIGOL_LINES)
    for r in results:
        assert r.n == n
        assert 0.0 <= r.base_rate <= 1.0
