"""Extra OddsAPIClient endpoints (player markets, fixture teams).

Kept in a mixin so adapters/odds_api.py stays under the 300-line limit.
Errors are NOT swallowed here: callers must tell "API said no data" (cacheable)
from "request failed" (must not be cached).
"""

from typing import Optional, Tuple

from core.odds_markets import PLAYER_BOOKED_BET_IDS


class OddsExtrasMixin:
    """Requires `_make_request` and `_parse_fixture_odds` from OddsAPIClient."""

    async def get_player_booked_odds(self, fixture_id: int) -> Optional["FixtureOdds"]:  # noqa: F821
        """Fetch "Player to be booked" odds; tries bet ids 102 then 251.

        Stops at the first id returning data (saves quota). Returns None when
        neither id has odds for the fixture. Raises OddsAPIError on failures.
        """
        for bet_id in PLAYER_BOOKED_BET_IDS:
            data = await self._make_request("/odds", {"fixture": fixture_id, "bet": bet_id})
            response = data.get("response") or []
            if not response:
                continue
            parsed = self._parse_fixture_odds(fixture_id, response)
            if parsed.bookmakers:
                return parsed
        return None

    async def get_fixture_teams(self, fixture_id: int) -> Optional[Tuple[str, str]]:
        """Return (home_name, away_name) for a fixture via /fixtures?id=."""
        data = await self._make_request("/fixtures", {"id": fixture_id})
        response = data.get("response") or []
        if not response:
            return None
        teams = response[0].get("teams", {})
        home = (teams.get("home") or {}).get("name")
        away = (teams.get("away") or {}).get("name")
        return (home, away) if home and away else None
