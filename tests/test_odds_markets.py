"""Bet-id mapping and OddsFetcher._get_bet_id_for_market (rule: no quote beats a wrong quote)."""

import pytest

from core.odds_fetcher import OddsFetcher
from core.odds_markets import resolve_bet_id, split_team_market


@pytest.mark.parametrize("market, side, expected", [
    ("Match Result", None, 1), ("Match Goals", None, 5), ("Both Teams to Score", None, 8),
    ("Exact Score", None, 10), ("Total Corners", None, 45), ("Total Cards", None, 80),
    ("Total Shots", None, 211), ("Total Shots on Goal", None, 87),
    # per-team: must NOT fall into the total-market ids
    ("Inter Corners", "home", 57), ("Inter Corners", "away", 58),
    ("Inter Cards", "home", 82), ("Inter Cards", "away", 83),
    ("Inter Goals", "home", 16), ("Inter Goals", "away", 17),
    # no team-level bet exists -> None
    ("Inter Shots", "home", None), ("Inter Shots on Goal", "away", None),
    # unknown side -> None, never the total id
    ("Inter Corners", None, None), ("Inter Cards", None, None),
    # player market never resolves to a match-level id (11 is 'Highest Scoring Half')
    ("Player Card - L. Martinez", None, None), ("Player Card - Total", "home", None),
])
def test_resolve_bet_id(market, side, expected):
    assert resolve_bet_id(market, side) == expected


def test_split_team_market():
    assert split_team_market("AC Milan Shots on Goal") == ("AC Milan", "shots on goal")
    assert split_team_market("Total Corners") is None
    assert split_team_market("Match Goals") is None


def test_fetcher_wrapper_delegates_and_never_returns_11():
    fetcher = OddsFetcher(odds_client=object(), redis_cache=None)
    assert fetcher._get_bet_id_for_market("Player Card - Bastoni") is None
    assert fetcher._get_bet_id_for_market("Roma Cards") is None
    assert fetcher._get_bet_id_for_market("Roma Cards", "away") == 83
    assert fetcher._get_bet_id_for_market("Total Cards") == 80
