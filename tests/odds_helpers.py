"""Test doubles for odds tests (no network, no Redis). Fixtures live in tests/fixtures/."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from adapters.odds_api import FixtureOdds, OddsAPIClient

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> Dict[str, Any]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class FakeOddsClient:
    """Replays a stored /odds payload, filtering by bet id like the real API."""

    def __init__(self, payload: Dict[str, Any], teams=("AS Roma", "Inter"), fail: bool = False):
        self.payload = payload
        self.teams = teams
        self.fail = fail
        self.calls: List[tuple] = []
        self._parser = OddsAPIClient.__new__(OddsAPIClient)  # parser only, no settings/network

    def _filtered(self, fixture_id: int, bet_ids: Optional[List[int]]) -> Optional[FixtureOdds]:
        response = json.loads(json.dumps(self.payload["response"]))
        for item in response:
            for bookmaker in item["bookmakers"]:
                bookmaker["bets"] = [b for b in bookmaker["bets"] if not bet_ids or b["id"] in bet_ids]
            item["bookmakers"] = [b for b in item["bookmakers"] if b["bets"]]
            item["fixture"]["id"] = fixture_id
        parsed = self._parser._parse_fixture_odds(fixture_id, response)
        return parsed if parsed.bookmakers else None

    async def get_fixture_odds(self, fixture_id, bet_ids=None, bookmaker_ids=None):
        self.calls.append(("odds", fixture_id, tuple(bet_ids or ())))
        return self._filtered(fixture_id, bet_ids)

    async def get_player_booked_odds(self, fixture_id):
        self.calls.append(("booked", fixture_id))
        if self.fail:
            raise RuntimeError("boom")
        return self._filtered(fixture_id, [102, 251])

    async def get_fixture_teams(self, fixture_id):
        self.calls.append(("teams", fixture_id))
        return self.teams


class DeadRedis:
    """Redis that raises on every call (worst-case offline)."""

    async def get_data(self, *a, **k):
        raise ConnectionError("redis down")

    async def set_data(self, *a, **k):
        raise ConnectionError("redis down")

    def get_team_roster(self, *a, **k):
        raise ConnectionError("redis down")
