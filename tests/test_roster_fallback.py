"""get_team_roster_with_fallback: Redis -> API, in-memory cache, never raises."""

import types

import pytest

from adapters.roster_fallback import clear_roster_memory, get_team_roster_with_fallback, player_from_api
from adapters.roster_service import get_team_roster_with_fallback as reexported
from tests.odds_helpers import DeadRedis, load_fixture


class FakeHTTP:
    def __init__(self, pages=None, fail=False):
        self.pages = pages or []
        self.fail = fail
        self.calls = []

    async def request(self, endpoint, params=None):
        self.calls.append((endpoint, dict(params or {})))
        if self.fail:
            raise RuntimeError("api down")
        page = params["page"]
        return {"response": self.pages[page - 1], "paging": {"current": page, "total": len(self.pages)}}


class RedisWithRoster:
    def get_team_roster(self, team_id, season):
        return [{"id": 1, "name": "From Redis"}]


class RedisEmpty:
    def get_team_roster(self, team_id, season):
        return None


def client(redis, http):
    return types.SimpleNamespace(redis_cache=redis, _http=http)


@pytest.fixture(autouse=True)
def _reset_memory():
    clear_roster_memory()
    yield
    clear_roster_memory()


def test_reexported_from_roster_service():
    assert reexported is get_team_roster_with_fallback


async def test_redis_hit_skips_api():
    http = FakeHTTP()
    roster = await get_team_roster_with_fallback(client(RedisWithRoster(), http), 505, 2026)
    assert roster == [{"id": 1, "name": "From Redis"}] and http.calls == []


async def test_redis_off_falls_back_to_api_with_pagination_and_domestic_stats():
    entries = load_fixture("players_team_505_page1.json")["response"]
    http = FakeHTTP(pages=[entries[:2], entries[2:]])
    roster = await get_team_roster_with_fallback(client(DeadRedis(), http), 505, 2026)

    assert [c[1]["page"] for c in http.calls] == [1, 2]
    assert all(c[0] == "/players" and c[1]["team"] == 505 and c[1]["season"] == 2026 for c in http.calls)
    assert len(roster) == 4
    akanji = roster[0]
    # fixture: CL entry (0 apps) + Serie A entry (4 apps, 1 yellow): only Serie A counts
    assert akanji["name"] == "M. Akanji" and akanji["appearances"] == 4 and akanji["yellow_cards"] == 1
    assert akanji["position"] == "Defender" and akanji["team_id"] == 505
    second = roster[1]   # fixture: CL 1 app/1 yellow + Serie A 3 apps/2 yellows -> domestic only
    assert second["appearances"] == 3 and second["yellow_cards"] == 2
    # analyzer keys always present
    for key in ("minutes", "fouls_committed", "tackles_total"):
        assert key in akanji


async def test_result_is_cached_in_memory():
    http = FakeHTTP(pages=[load_fixture("players_team_505_page1.json")["response"]])
    api = client(RedisEmpty(), http)
    first = await get_team_roster_with_fallback(api, 505, 2026)
    second = await get_team_roster_with_fallback(api, 505, 2026)
    assert first is second and len(http.calls) == 1


async def test_api_failure_returns_empty_list_and_is_negatively_cached(capsys):
    http = FakeHTTP(fail=True)
    api = client(DeadRedis(), http)
    assert await get_team_roster_with_fallback(api, 505, 2026) == []
    assert await get_team_roster_with_fallback(api, 505, 2026) == []
    assert len(http.calls) == 1
    assert "Fallback roster API fallito" in capsys.readouterr().out


async def test_client_without_http_returns_empty():
    assert await get_team_roster_with_fallback(types.SimpleNamespace(redis_cache=None), 1, 2026) == []


def test_player_from_api_ignores_other_teams_and_uses_all_entries_when_no_domestic():
    entry = {"player": {"id": 9, "name": "X"}, "statistics": [
        {"team": {"id": 1}, "league": {"id": 2}, "games": {"appearences": 2, "minutes": 100, "position": "Midfielder"},
         "cards": {"yellow": 3}, "fouls": {"committed": 4}, "tackles": {"total": 5}},
        {"team": {"id": 99}, "league": {"id": 135}, "games": {"appearences": 30}, "cards": {"yellow": 30}},
    ]}
    player = player_from_api(entry, 1, domestic_ids={135})
    assert player["appearances"] == 2 and player["yellow_cards"] == 3 and player["tackles_total"] == 5
    assert player_from_api(entry, 555, {135}) is None
