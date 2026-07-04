"""
Tests for the point-in-time replay engine.

The headline test is `test_no_data_leakage`: it proves that the stats handed to
the model for a match reflect ONLY earlier matches — the whole backtest is
worthless if this fails.
"""

from backtest.engine import (
    TeamAccumulator,
    iter_scored_matches,
    ScoredMatch,
)


def _fixture(date, fid, home_id, home, away_id, away, hg, ag, status="FT"):
    return {
        "fixture_id": fid, "date": date, "status": status, "round": "",
        "home_id": home_id, "home_name": home,
        "away_id": away_id, "away_name": away,
        "home_goals": hg, "away_goals": ag,
    }


# ── TeamAccumulator ───────────────────────────────────────────────────────────

def test_accumulator_tracks_results():
    acc = TeamAccumulator(team_id=1, name="Alpha")
    acc.update(2, 0)   # win, clean sheet
    acc.update(1, 1)   # draw
    acc.update(0, 3)   # loss, failed to score

    assert acc.matches_played == 3
    assert acc.goals_for == 3
    assert acc.goals_against == 4
    assert acc.wins == 1 and acc.draws == 1 and acc.losses == 1
    assert acc.clean_sheets == 1
    assert acc.failed_to_score == 1
    assert acc.form == ["W", "D", "L"]


def test_accumulator_to_team_stats():
    acc = TeamAccumulator(team_id=7, name="Beta")
    acc.update(3, 0)
    acc.update(2, 1)
    ts = acc.to_team_stats()

    assert ts.team.id == 7
    assert ts.matches_played == 2
    assert ts.goals_for == 5
    assert ts.goals_per_game == 2.5
    assert ts.clean_sheets == 1
    assert ts.form == "WW"
    assert ts.recent_form_points == 6  # two wins


# ── no data leakage (the critical property) ──────────────────────────────────

def test_no_data_leakage():
    """
    Alpha plays 4 matches (always home), scoring its match number and conceding 0.
    Each snapshot handed to the model must exclude the current match and include
    every earlier one.
    """
    fixtures = [
        _fixture("2025-01-01T12:00:00Z", 1, 100, "Alpha", 200, "B", 1, 0),
        _fixture("2025-01-08T12:00:00Z", 2, 100, "Alpha", 300, "C", 2, 0),
        _fixture("2025-01-15T12:00:00Z", 3, 100, "Alpha", 400, "D", 3, 0),
        _fixture("2025-01-22T12:00:00Z", 4, 100, "Alpha", 500, "E", 4, 0),
    ]
    # min_matches=0 so every match is yielded and we can inspect each snapshot.
    snapshots = list(iter_scored_matches(fixtures, min_matches=0))
    assert len(snapshots) == 4

    # Alpha is always the home team; check its pre-match tally per game.
    expected = [
        (0, 0),   # before match 1: nothing
        (1, 1),   # before match 2: 1 game, 1 goal
        (2, 3),   # before match 3: 2 games, 1+2 goals
        (3, 6),   # before match 4: 3 games, 1+2+3 goals
    ]
    for snap, (mp, gf) in zip(snapshots, expected):
        assert snap.home_stats.matches_played == mp
        assert snap.home_stats.goals_for == gf
        # And crucially the current match's goals are NOT yet included.
        assert snap.home_stats.goals_for != gf + snap.home_goals or snap.home_goals == 0


# ── min_matches gating ────────────────────────────────────────────────────────

def _round_robin(team_ids, names, start_fid=1):
    """Every team plays every other once (home/away arbitrary), 1-0 home wins."""
    fixtures = []
    fid = start_fid
    day = 1
    for i in range(len(team_ids)):
        for j in range(len(team_ids)):
            if i == j:
                continue
            fixtures.append(_fixture(
                f"2025-02-{day:02d}T12:00:00Z", fid,
                team_ids[i], names[i], team_ids[j], names[j], 1, 0,
            ))
            fid += 1
            day += 1
    return fixtures


def test_min_matches_gates_early_games():
    ids = [1, 2, 3, 4]
    names = ["A", "B", "C", "D"]
    fixtures = _round_robin(ids, names)

    scored = list(iter_scored_matches(fixtures, min_matches=2))
    # Every yielded match must have both teams already at >= 2 games.
    assert scored, "expected some matches to survive the gate"
    for m in scored:
        assert m.home_stats.matches_played >= 2
        assert m.away_stats.matches_played >= 2


def test_non_finished_matches_are_skipped():
    fixtures = [
        _fixture("2025-01-01T12:00:00Z", 1, 1, "A", 2, "B", 1, 0, status="NS"),
        _fixture("2025-01-02T12:00:00Z", 2, 1, "A", 3, "C", None, None, status="NS"),
    ]
    assert list(iter_scored_matches(fixtures, min_matches=0)) == []


# ── ScoredMatch outcome helpers ───────────────────────────────────────────────

def test_scored_match_outcomes():
    from core.models import Team, TeamStats

    def blank(name):
        return TeamStats(
            team=Team(id=0, name=name), matches_played=5, wins=2, draws=1, losses=2,
            goals_for=8, goals_against=7, shots_total=0, shots_on_target=0,
            corners=0, yellow_cards=0, red_cards=0,
        )

    m = ScoredMatch("2025-01-01", "H", "A", blank("H"), blank("A"), home_goals=2, away_goals=1)
    assert m.total_goals == 3
    assert m.result == "1"
    assert m.over(2.5) == 1
    assert m.over(3.5) == 0
    assert m.btts == 1

    draw = ScoredMatch("2025-01-01", "H", "A", blank("H"), blank("A"), 0, 0)
    assert draw.result == "X"
    assert draw.btts == 0
    assert draw.over(1.5) == 0
