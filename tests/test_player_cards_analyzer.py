"""Tests for the live PlayerCardsAnalyzer (rosters mocked, no network/DB)."""

import asyncio
from datetime import datetime
from types import SimpleNamespace

import pytest

import analyzers.player_cards_analyzer as mod
from analyzers.player_cards_analyzer import PlayerCardsAnalyzer, merge_roster_history
from core.config import get_settings


def _fixture():
    return SimpleNamespace(
        id=1, date=datetime(2026, 9, 20),
        home_team=SimpleNamespace(id=10, name="Home"),
        away_team=SimpleNamespace(id=20, name="Away"),
    )


def _p(name, pos, apps, yellows, fouls=0, minutes=900):
    return {"id": sum(map(ord, name)), "name": name, "position": pos, "appearances": apps,
            "yellow_cards": yellows, "fouls_committed": fouls, "minutes": minutes}


def _run(monkeypatch, rosters, league="Serie A"):
    """rosters: {team_id: current roster} plus optional {(team_id, season): roster}."""
    current_season = get_settings().default_season

    async def fake(api_client, team_id, season):
        if season == current_season:
            return rosters.get(team_id, [])
        return rosters.get((team_id, season), [])
    monkeypatch.setattr(mod, "get_team_roster_with_fallback", fake)
    return asyncio.run(PlayerCardsAnalyzer().analyze_match_players(_fixture(), [], league, object()))


def test_empty_rosters_return_empty_list(monkeypatch):
    assert _run(monkeypatch, {}) == []


def test_roster_failure_does_not_crash(monkeypatch):
    async def boom(api_client, team_id, season):
        raise RuntimeError("no roster")
    monkeypatch.setattr(mod, "get_team_roster_with_fallback", boom)
    assert asyncio.run(PlayerCardsAnalyzer().analyze_match_players(_fixture(), [], "Serie A", None)) == []


def test_keepers_and_players_without_minutes_are_skipped(monkeypatch):
    roster = [_p("Keeper", "Goalkeeper", 30, 5), _p("Bench", "Defender", 5, 4, minutes=0), _p("Clean", "Forward", 30, 0, fouls=10),
              _p("Def", "Defender", 30, 9, fouls=60)]
    picks = _run(monkeypatch, {10: roster})
    # keeper, zero-minute and low-probability (below the pick threshold) players are all dropped
    assert [p.market for p in picks] == ["Player Card - Def"]


def test_low_sample_player_is_shrunk_and_probabilities_are_sane(monkeypatch):
    roster = [_p("Fluke", "Defender", 3, 3, minutes=270), _p("Regular", "Defender", 34, 12, fouls=50)]
    picks = _run(monkeypatch, {10: roster})
    by_name = {p.market: p for p in picks}
    assert all(0 < p.percentage <= 90 for p in picks)
    # 3/3 yellows in 3 apps is NOT ~100%: it stays close to the position prior
    assert by_name["Player Card - Fluke"].percentage < 30


def test_pick_fields_and_ordering(monkeypatch):
    roster = [_p("A", "Defender", 30, 12, fouls=60), _p("B", "Midfielder", 30, 6, fouls=40)]
    picks = _run(monkeypatch, {10: roster, 20: [_p("C", "Defender", 30, 10, fouls=55)]})
    assert [p.percentage for p in picks] == sorted((p.percentage for p in picks), reverse=True)
    top = picks[0]
    assert top.selection == "Yellow Card" and top.real_odds is None and top.bookmaker is None
    assert top.player_team in ("Home", "Away") and top.league == "Serie A"
    assert top.confidence in ("HIGH", "MEDIUM", "LOW")


def test_european_cups_are_skipped(monkeypatch):
    roster = [_p("A", "Defender", 30, 12)]
    assert _run(monkeypatch, {10: roster}, league="Champions League") == []


# ── previous-season history ───────────────────────────────────────────────────

def test_previous_season_history_ranks_a_proven_booker_first(monkeypatch):
    prev = get_settings().default_season - 1
    current = [_p("Booked", "Defender", 3, 0, fouls=6), _p("Clean", "Defender", 3, 0, fouls=6)]
    history = [_p("Booked", "Defender", 34, 14, fouls=60)]
    without = {p.market: p.percentage for p in _run(monkeypatch, {10: current})}
    with_hist = {p.market: p.percentage for p in _run(monkeypatch, {10: current, (10, prev): history})}
    assert with_hist["Player Card - Booked"] > with_hist["Player Card - Clean"]
    assert with_hist["Player Card - Booked"] > without["Player Card - Booked"] + 3


def test_players_who_left_the_club_are_ignored(monkeypatch):
    prev = get_settings().default_season - 1
    current = [_p("Stays", "Defender", 4, 1, fouls=8)]
    history = [_p("Gone", "Defender", 34, 20, fouls=90)]
    picks = _run(monkeypatch, {10: current, (10, prev): history})
    assert all("Gone" not in p.market for p in picks)


def test_previous_season_failure_falls_back_to_current_only(monkeypatch):
    current_season = get_settings().default_season

    async def fake(api_client, team_id, season):
        if season != current_season:
            raise RuntimeError("no history")
        return [_p("Def", "Defender", 30, 9, fouls=60)] if team_id == 10 else []
    monkeypatch.setattr(mod, "get_team_roster_with_fallback", fake)
    picks = asyncio.run(PlayerCardsAnalyzer().analyze_match_players(_fixture(), [], "Serie A", None))
    assert [p.market for p in picks] == ["Player Card - Def"]


def test_merge_sums_totals_and_keeps_fouls_only_when_complete():
    cur = [_p("A", "Defender", 4, 1, fouls=8, minutes=300), _p("B", "Defender", 4, 1, fouls=0, minutes=300)]
    old = [_p("A", "Defender", 30, 9, fouls=40, minutes=2500), _p("B", "Defender", 30, 9, fouls=40, minutes=2500)]
    a, b = merge_roster_history(cur, old)
    assert (a["appearances"], a["yellow_cards"], a["minutes"], a["fouls_committed"]) == (34, 10, 2800, 48)
    assert b["fouls_committed"] == 0      # current season lacks fouls -> total is treated as missing
