"""Live match service — real-time fixture data and in-match statistics."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from adapters.http_client import FootballHTTPClient


class LiveMatchService:
    """
    Responsible for live match data only.

    Single responsibility: current live fixtures and per-fixture
    in-progress statistics.  No caching needed — data is always fresh.
    """

    def __init__(self, http: FootballHTTPClient):
        self._http = http

    async def get_live_fixtures(
        self, leagues: Optional[List[int]] = None
    ) -> List[Dict[str, Any]]:
        """Return today's live fixtures, optionally filtered by league IDs."""
        try:
            data = await self._http.request("/fixtures", {"live": "all"})
            if not data.get("response"):
                return []

            today = datetime.now(timezone.utc).date()
            results = []

            for fd in data["response"]:
                fi = fd.get("fixture", {})
                li = fd.get("league", {})
                ti = fd.get("teams", {})
                si = fd.get("score", {})

                # Date filter
                date_str = fi.get("date", "")
                try:
                    fixture_date = datetime.fromisoformat(
                        date_str.replace("Z", "+00:00")
                    ).date()
                except Exception:
                    fixture_date = None

                if fixture_date != today:
                    continue

                if leagues and li.get("id") not in leagues:
                    continue

                results.append({
                    "id": fi.get("id"),
                    "date": fi.get("date"),
                    "status": fi.get("status", {}).get("short"),
                    "elapsed": fi.get("status", {}).get("elapsed"),
                    "venue": fi.get("venue", {}).get("name"),
                    "league": {
                        "id": li.get("id"),
                        "name": li.get("name"),
                        "country": li.get("country"),
                        "flag": li.get("flag"),
                        "logo": li.get("logo"),
                    },
                    "home_team": {
                        "id": ti.get("home", {}).get("id"),
                        "name": ti.get("home", {}).get("name"),
                        "logo": ti.get("home", {}).get("logo"),
                    },
                    "away_team": {
                        "id": ti.get("away", {}).get("id"),
                        "name": ti.get("away", {}).get("name"),
                        "logo": ti.get("away", {}).get("logo"),
                    },
                    "score": {
                        "home": si.get("fulltime", {}).get("home"),
                        "away": si.get("fulltime", {}).get("away"),
                        "halftime_home": si.get("halftime", {}).get("home"),
                        "halftime_away": si.get("halftime", {}).get("away"),
                    },
                })

            return results

        except Exception as exc:
            print(f"⚠️ Error fetching live fixtures: {exc}")
            return []

    async def get_live_match_statistics(
        self, fixture_id: int
    ) -> Dict[str, Dict[str, Any]]:
        """Return home/away in-progress statistics for a live fixture."""
        try:
            data = await self._http.request(
                "/fixtures/statistics", {"fixture": fixture_id}
            )
            if not data.get("response"):
                return {}

            stats_data = data["response"]
            live_stats: Dict[str, Dict] = {"home": {}, "away": {}}

            for i, team_entry in enumerate(stats_data):
                key = "home" if i == 0 else "away"
                for stat in team_entry.get("statistics", []):
                    stat_type = stat.get("type", "")
                    value = stat.get("value")
                    if isinstance(value, str) and "%" in value:
                        try:
                            value = float(value.replace("%", ""))
                        except Exception:
                            value = 0

                    mapping = {
                        "Shots on Goal": "shots_on_target",
                        "Total Shots": "total_shots",
                        "Ball Possession": "possession",
                        "Corner Kicks": "corners",
                        "Offsides": "offsides",
                        "Yellow Cards": "yellow_cards",
                        "Red Cards": "red_cards",
                        "Fouls": "fouls",
                        "Passes %": "pass_accuracy",
                    }
                    mapped_key = mapping.get(stat_type)
                    if mapped_key:
                        live_stats[key][mapped_key] = value or 0

            return live_stats

        except Exception as exc:
            print(f"⚠️ Error fetching live match statistics: {exc}")
            return {}
