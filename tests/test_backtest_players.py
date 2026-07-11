"""Tests for player data parsing and the player booking model."""

from backtest.player_data import extract_players
from backtest.player_cards import run_player_cards_backtest, _ref_name


# ── parsing ───────────────────────────────────────────────────────────────────

def _payload():
    return [
        {"team": {"id": 1}, "players": [
            {"player": {"id": 10, "name": "Def One"}, "statistics": [
                {"games": {"minutes": 90, "position": "D"},
                 "cards": {"yellow": 1, "red": 0}, "fouls": {"committed": 2}}]},
            {"player": {"id": 11, "name": "Sub"}, "statistics": [
                {"games": {"minutes": None, "position": "M"},
                 "cards": {"yellow": 0}, "fouls": {"committed": None}}]},
        ]},
    ]


def test_extract_players():
    rows = extract_players(_payload())
    assert len(rows) == 2
    d = rows[0]
    assert d["player_id"] == 10 and d["team_id"] == 1
    assert d["minutes"] == 90 and d["position"] == "D" and d["yellow"] == 1
    assert rows[1]["minutes"] is None   # unused sub


def test_extract_players_empty():
    assert extract_players([]) == []


def test_ref_name():
    assert _ref_name("M. Guida, Italy") == "M. Guida"
    assert _ref_name(None) == ""


# ── backtest ──────────────────────────────────────────────────────────────────

def _season():
    """8 teams, several rounds; a couple of 'dirty' players booked often."""
    import itertools
    teams = list(range(1, 9))
    # player ids: team t has players t*10+0..10 (11 players)
    fixtures, pmap, fid, day = [], {}, 1, 1
    dirty = {t * 10 + 1 for t in teams}   # one habitual booker per team
    for _ in range(6):
        for home, away in itertools.permutations(teams, 2):
            roster = []
            for team in (home, away):
                for slot in range(11):
                    pid = team * 10 + slot
                    pos = "D" if slot < 4 else "M" if slot < 8 else "F"
                    booked = 1 if (pid in dirty and (fid + slot) % 2 == 0) else (1 if (fid + pid) % 7 == 0 else 0)
                    roster.append({
                        "player_id": pid, "name": f"P{pid}", "team_id": team,
                        "minutes": 90, "position": pos,
                        "yellow": booked, "fouls": 2,
                    })
            fixtures.append({
                "fixture_id": fid, "date": f"2024-0{1+day//28}-{1+day%28:02d}T12:00:00Z",
                "status": "FT", "season": 2024,
                "home_id": home, "away_id": away, "referee": "Ref A",
            })
            pmap[str(fid)] = roster
            fid += 1
            day += 1
    return fixtures, pmap


def test_player_cards_backtest_runs():
    fx, pmap = _season()
    rep = run_player_cards_backtest(fx, pmap, min_apps=2)
    assert rep.n_pairs > 0 and rep.n_matches > 0
    assert 0.0 < rep.base_rate < 1.0
    assert 0.0 <= rep.precision_at_k <= 1.0
    # the model should give habitual bookers higher prob than average
    assert rep.mean_p_booked >= rep.mean_p_unbooked


def test_player_cards_respects_min_apps():
    fx, pmap = _season()
    strict = run_player_cards_backtest(fx, pmap, min_apps=10)
    lenient = run_player_cards_backtest(fx, pmap, min_apps=1)
    assert lenient.n_pairs >= strict.n_pairs
