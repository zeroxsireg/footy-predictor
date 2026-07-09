"""Tests for xG parsing and the goals-vs-xG comparison."""

from backtest.xg_data import _extract_xg
from backtest.xg_compare import run_xg_comparison


# ── xG parsing ────────────────────────────────────────────────────────────────

def _stats_entry(team_id, xg_value):
    return {
        "team": {"id": team_id},
        "statistics": [
            {"type": "Total Shots", "value": 12},
            {"type": "expected_goals", "value": xg_value},
            {"type": "Ball Possession", "value": "55%"},
        ],
    }


def test_extract_xg_maps_home_and_away():
    resp = [_stats_entry(10, "1.30"), _stats_entry(20, "0.70")]
    home_xg, away_xg = _extract_xg(resp, home_id=10, away_id=20)
    assert home_xg == 1.30
    assert away_xg == 0.70


def test_extract_xg_handles_missing_value():
    resp = [_stats_entry(10, None), _stats_entry(20, "")]
    home_xg, away_xg = _extract_xg(resp, home_id=10, away_id=20)
    assert home_xg is None and away_xg is None


def test_extract_xg_handles_empty_response():
    assert _extract_xg([], 1, 2) == (None, None)


def test_extract_xg_absent_stat_type():
    resp = [{"team": {"id": 10}, "statistics": [{"type": "Total Shots", "value": 5}]}]
    home_xg, away_xg = _extract_xg(resp, 10, 20)
    assert home_xg is None and away_xg is None


# ── comparison ────────────────────────────────────────────────────────────────

def _season():
    teams = [(1, "A"), (2, "B"), (3, "C"), (4, "D")]
    scores = [(2, 1), (0, 0), (3, 1), (1, 1), (2, 0), (1, 2)]
    fixtures, xg_map, fid, day, si = [], {}, 1, 1, 0
    for _ in range(6):  # several rounds so teams pass min_matches
        for i in range(len(teams)):
            for j in range(len(teams)):
                if i == j:
                    continue
                hg, ag = scores[si % len(scores)]
                si += 1
                fixtures.append({
                    "fixture_id": fid, "date": f"2024-0{1+day//28}-{1+day%28:02d}T12:00:00Z",
                    "status": "FT", "home_id": teams[i][0], "home_name": teams[i][1],
                    "away_id": teams[j][0], "away_name": teams[j][1],
                    "home_goals": hg, "away_goals": ag,
                })
                # xG roughly tracks goals but not exactly
                xg_map[str(fid)] = {"home_xg": hg + 0.3, "away_xg": ag + 0.2}
                fid += 1
                day += 1
    return fixtures, xg_map


def test_xg_comparison_scores_both_models():
    fixtures, xg_map = _season()
    cmp = run_xg_comparison(fixtures, xg_map, min_matches=2)
    assert cmp.n > 0
    assert set(cmp.models) == {"Gol", "xG"}
    assert len(cmp.models["Gol"].binary) == 4
    for name in ("Gol", "xG"):
        assert cmp.models[name].result_1x2.n == cmp.n


def test_missing_xg_falls_back_to_goals():
    fixtures, xg_map = _season()
    # Drop xG for half the matches -> should count as missing, not crash.
    for fid in list(xg_map)[::2]:
        xg_map[fid] = {"home_xg": None, "away_xg": None}
    cmp = run_xg_comparison(fixtures, xg_map, min_matches=2)
    assert cmp.xg_missing > 0
    assert cmp.n > 0


def test_score_seasons_filter_limits_scored_matches():
    # Two seasons of fixtures; only the target season is scored, the other only
    # builds history.
    fx_a, xg_a = _season()
    fx_b, xg_b = _season()
    for r in fx_a:
        r["season"] = 2023
    for r in fx_b:
        r["season"] = 2024
        r["fixture_id"] += 10000  # keep ids unique across seasons
    xg_all = {**xg_a, **{str(int(k) + 10000): v for k, v in xg_b.items()}}

    full = run_xg_comparison(fx_a + fx_b, xg_all, min_matches=2)
    only_2024 = run_xg_comparison(
        fx_a + fx_b, xg_all, min_matches=2, score_seasons={2024},
    )
    assert only_2024.n < full.n
    assert only_2024.n > 0
