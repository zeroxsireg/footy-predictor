"""The default season must come from Settings (SSOT), never from a literal."""

import asyncio
from types import SimpleNamespace

import pytest

from services import data_service
from utils import team_id_manager
from utils.team_id_manager import TeamIDManager

FAKE_SEASON = 2031


@pytest.fixture
def fake_settings(monkeypatch):
    settings = SimpleNamespace(default_season=FAKE_SEASON)
    monkeypatch.setattr(team_id_manager, "get_settings", lambda: settings)
    monkeypatch.setattr(data_service, "get_settings", lambda: settings)


@pytest.mark.parametrize("method,league_id", [
    ("get_serie_a_teams", 135),
    ("get_premier_league_teams", 39),
    ("get_la_liga_teams", 140),
    ("get_bundesliga_teams", 78),
])
def test_team_id_manager_uses_settings_season(fake_settings, method, league_id):
    manager = TeamIDManager(api_client=None)
    calls = []

    async def fake_get_league_teams(lid, season):
        calls.append((lid, season))
        return {}

    manager.get_league_teams = fake_get_league_teams
    asyncio.run(getattr(manager, method)())
    asyncio.run(getattr(manager, method)(2020))

    assert calls == [(league_id, FAKE_SEASON), (league_id, 2020)]


def test_data_service_current_season_uses_settings(fake_settings):
    service = data_service.DataService(redis_cache=None)
    assert service.current_season == FAKE_SEASON
