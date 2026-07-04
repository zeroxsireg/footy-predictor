"""End-to-end smoke test: a synthetic mini-season runs through the full pipeline."""

from backtest.runner import run_backtest


def _synthetic_season():
    """
    Four teams, double round-robin, deterministic-but-varied scorelines so that
    every market has a mix of outcomes.
    """
    teams = [(1, "A"), (2, "B"), (3, "C"), (4, "D")]
    scorelines = [(2, 1), (0, 0), (3, 1), (1, 1), (2, 0), (1, 2)]
    fixtures = []
    fid = 1
    day = 1
    si = 0
    for i in range(len(teams)):
        for j in range(len(teams)):
            if i == j:
                continue
            hg, ag = scorelines[si % len(scorelines)]
            si += 1
            fixtures.append({
                "fixture_id": fid,
                "date": f"2025-03-{day:02d}T12:00:00Z",
                "status": "FT", "round": "",
                "home_id": teams[i][0], "home_name": teams[i][1],
                "away_id": teams[j][0], "away_name": teams[j][1],
                "home_goals": hg, "away_goals": ag,
            })
            fid += 1
            day += 1
    return fixtures


def test_run_backtest_produces_scored_report():
    report = run_backtest(_synthetic_season(), league_id=135, season=2025, min_matches=2)

    assert report.total_matches_scored > 0
    assert len(report.binary) == 4
    markets = {r.market for r in report.binary}
    assert markets == {"Over 1.5 Goals", "Over 2.5 Goals", "Over 3.5 Goals", "BTTS Yes"}

    for r in report.binary:
        assert r.n == report.total_matches_scored
        assert 0.0 <= r.hit_rate <= 1.0
        assert 0.0 <= r.avg_prediction <= 1.0
        assert 0.0 <= r.base_rate <= 1.0
        assert r.brier >= 0.0

    m = report.result_1x2
    assert m.n == report.total_matches_scored
    assert 0.0 <= m.hit_rate <= 1.0
    assert abs(sum(m.per_class_base_rate.values()) - 1.0) < 0.01


def test_min_matches_reduces_sample():
    season = _synthetic_season()
    lenient = run_backtest(season, min_matches=1).total_matches_scored
    strict = run_backtest(season, min_matches=3).total_matches_scored
    assert lenient >= strict
