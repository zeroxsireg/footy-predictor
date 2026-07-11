"""
Football API adapter — public facade for all API operations.

This module is the only stable interface that the rest of the codebase
should import.  Internally it composes four focused services:

  FootballHTTPClient  — rate-limited HTTP transport
  TeamStatsService    — season stats per team
  RosterService       — squad / player data
  LiveMatchService    — real-time match data

Adding a new data source means adding a new service and wiring it here;
nothing else needs to change.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

import pytz

from core.config import get_settings
from core.models import Team, Fixture, TeamStats

from adapters.http_client import FootballHTTPClient, FootballAPIError
from adapters.team_stats_service import TeamStatsService
from adapters.roster_service import RosterService
from adapters.live_service import LiveMatchService

# Re-export so existing callers can still `from adapters.football_api import FootballAPIError`
__all__ = ["FootballAPIClient", "FootballAPIError"]


class FootballAPIClient:
    """
    Stable public API for all football data.

    Instantiate once per request/session; internal services share the
    same HTTP client instance (and therefore the same rate-limit state).
    """

    # Known league IDs — avoid a round-trip for common leagues
    _KNOWN_LEAGUES: Dict[tuple, int] = {
        ("Italy", "Serie A"): 135,
        ("England", "Premier League"): 39,
        ("Spain", "La Liga"): 140,
        ("Germany", "Bundesliga"): 78,
        ("UEFA", "Champions League"): 2,
        ("UEFA", "Europa League"): 3,
    }

    def __init__(self):
        from utils.redis_cache import get_redis_cache
        self.redis_cache = get_redis_cache()

        self._http = FootballHTTPClient()
        self._team_stats_svc = TeamStatsService(self._http, self.redis_cache)
        self._roster_svc = RosterService(self._http, self.redis_cache)
        self._live_svc = LiveMatchService(self._http)

        self._league_cache: Dict[tuple, int] = dict(self._KNOWN_LEAGUES)
        self.settings = get_settings()

    # ── league / fixture methods (stay here — they're coordination logic) ─────

    async def get_league_id(
        self, country: str = None, league_name: str = None, season: int = None
    ) -> int:
        country = country or self.settings.default_country
        league_name = league_name or self.settings.default_league
        season = season or self.settings.default_season

        key = (country, league_name)
        if key in self._league_cache:
            return self._league_cache[key]

        if country == "UEFA":
            raise FootballAPIError(f"UEFA competition not supported: {league_name}")

        data = await self._http.request(
            "/leagues", {"country": country, "name": league_name, "season": season}
        )
        if not data["response"]:
            raise FootballAPIError(f"League not found: {league_name} in {country}")

        league_id = data["response"][0]["league"]["id"]
        self._league_cache[key] = league_id
        return league_id

    async def get_league_standings(
        self, league_id: int, season: int
    ) -> Optional[List[Dict]]:
        try:
            data = await self._http.request(
                "/standings", {"league": league_id, "season": season}
            )
            if data.get("response") and data["response"]:
                standings = (
                    data["response"][0].get("league", {}).get("standings", [])
                )
                return standings[0] if standings else None
        except Exception as exc:
            print(f"⚠️ Error fetching league standings: {exc}")
        return None

    async def get_next_round_fixtures(
        self, league_id: int = None, season: int = None, country: str = None
    ) -> tuple:
        if league_id is None:
            league_id = await self.get_league_id()

        season = season or self.settings.default_season
        country = country or self.settings.default_country

        data = await self._http.request(
            "/fixtures", {"league": league_id, "season": season, "next": "15"}
        )
        if not data.get("response"):
            data = await self._http.request(
                "/fixtures", {"league": league_id, "season": season, "last": "15"}
            )
        if not data.get("response"):
            raise FootballAPIError(
                f"No fixtures found for league {league_id} season {season}"
            )

        fixtures = []
        next_round = None
        for fd in data["response"]:
            fixture = self._parse_fixture(fd, country)
            fixtures.append(fixture)
            if next_round is None:
                next_round = self._extract_round(fd)

        if next_round and len(fixtures) > 10:
            filtered = []
            for fd in data["response"]:
                if self._extract_round(fd) == next_round:
                    filtered.append(self._parse_fixture(fd, country))
            if filtered:
                fixtures = filtered

        return fixtures, next_round or 1

    async def get_team_fixtures(
        self, team_id: int, season: int, status: str = None
    ) -> List[Fixture]:
        try:
            params: Dict[str, Any] = {
                "team": team_id, "season": season, "timezone": "Europe/Rome"
            }
            if status:
                params["status"] = status

            data = await self._http.request("/fixtures", params)
            if not data.get("response"):
                return []

            local_tz = pytz.timezone("Europe/Rome")
            fixtures = []
            for fd in data["response"]:
                fi = fd.get("fixture", {})
                ti = fd.get("teams", {})

                date_str = fi.get("date", "")
                try:
                    dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                    if dt.tzinfo is None:
                        dt = pytz.UTC.localize(dt)
                    dt = dt.astimezone(local_tz)
                except Exception:
                    dt = datetime.now(local_tz)

                fixtures.append(Fixture(
                    id=fi.get("id", 0),
                    date=dt,
                    status=fi.get("status", {}).get("short", "NS"),
                    home_team=Team(
                        id=ti.get("home", {}).get("id", 0),
                        name=ti.get("home", {}).get("name", "Unknown"),
                        logo=ti.get("home", {}).get("logo", ""),
                    ),
                    away_team=Team(
                        id=ti.get("away", {}).get("id", 0),
                        name=ti.get("away", {}).get("name", "Unknown"),
                        logo=ti.get("away", {}).get("logo", ""),
                    ),
                    venue=fd.get("venue", {}).get("name", ""),
                ))
            return fixtures
        except Exception as exc:
            print(f"⚠️ Error fetching team fixtures: {exc}")
            return []

    async def get_teams(
        self, country: str, league_name: str, season: int, league_id: int = None
    ) -> List[Team]:
        try:
            if league_id is None:
                league_id = await self.get_league_id(country, league_name, season)
            if not league_id:
                return []

            cache_key = f"teams:{league_id}:{season}"
            cached = await self.redis_cache.get_data(cache_key)
            if cached:
                print(f"📋 Using cached teams for {league_name}")
                return [Team(id=d["id"], name=d["name"], logo=d.get("logo")) for d in cached]

            print(f"🔄 Fetching teams for {league_name} from API...")
            data = await self._http.request("/teams", {"league": league_id, "season": season})
            if not data.get("response"):
                return []

            teams = [
                Team(id=ti["team"]["id"], name=ti["team"]["name"], logo=ti["team"]["logo"])
                for ti in data["response"]
            ]
            team_data_list = [
                {"id": t.id, "name": t.name, "logo": t.logo} for t in teams
            ]

            if league_name in ("Champions League", "Europa League") and season == 2025:
                teams = self._filter_european_competition_teams(teams, league_name)
                print(f"🏆 Filtered {league_name} teams to main tournament: {len(teams)} teams")
                names = {t.name for t in teams}
                team_data_list = [d for d in team_data_list if d["name"] in names]

            await self.redis_cache.set_data(cache_key, team_data_list, "team_metadata")
            print(f"✅ Fetched {len(teams)} teams for {league_name}")
            return teams

        except Exception as exc:
            print(f"❌ Error fetching teams: {exc}")
            return []

    # ── delegates to services ─────────────────────────────────────────────────

    async def get_team_statistics(
        self, team_id: int, league_id: int = None, season: int = None
    ) -> TeamStats:
        if league_id is None:
            league_id = await self.get_league_id()
        season = season or self.settings.default_season
        return await self._team_stats_svc.get_team_statistics(team_id, league_id, season)

    async def force_update_team_statistics(
        self, team_id: int, league_id: int, season: int
    ) -> Optional[TeamStats]:
        return await self._team_stats_svc.force_update(team_id, league_id, season)

    async def get_team_squad(
        self, team_id: int, season: int, auto_refresh: bool = True
    ) -> List[Dict]:
        return await self._roster_svc.get_team_squad(team_id, season, auto_refresh)

    async def get_team_players(self, team_id: int, season: int) -> List[Dict]:
        return await self._roster_svc.get_team_players(team_id, season)

    async def get_team_roster_fast(self, team_id: int, season: int) -> List[Dict]:
        return await self._roster_svc.get_team_roster_fast(team_id, season)

    async def get_player_statistics(
        self, player_id: int, league_id: int, season: int
    ) -> Dict:
        return await self._roster_svc.get_player_statistics(player_id, league_id, season)

    async def force_update_team_roster(self, team_id: int, season: int) -> bool:
        return await self._roster_svc.force_update_roster(team_id, season)

    async def force_update_player_statistics(
        self, player_id: int, league_id: int, season: int
    ) -> bool:
        return await self._roster_svc.force_update_player_statistics(
            player_id, league_id, season
        )

    async def get_live_fixtures(
        self, leagues: List[int] = None
    ) -> List[Dict[str, Any]]:
        return await self._live_svc.get_live_fixtures(leagues)

    async def get_live_match_statistics(self, fixture_id: int) -> Dict[str, Any]:
        return await self._live_svc.get_live_match_statistics(fixture_id)

    # ── parsing helpers ───────────────────────────────────────────────────────

    def _parse_fixture(self, fd: Dict[str, Any], country: str = "Italy") -> Fixture:
        fi = fd["fixture"]
        ti = fd["teams"]

        tz_map = {
            "Italy": "Europe/Rome", "England": "Europe/London",
            "Spain": "Europe/Madrid", "Germany": "Europe/Berlin",
            "France": "Europe/Paris", "Netherlands": "Europe/Amsterdam",
            "Portugal": "Europe/Lisbon", "Brazil": "America/Sao_Paulo",
        }
        raw = fi["date"]
        if raw.endswith("Z"):
            utc = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        elif "+" in raw or raw.count("-") > 2:
            utc = datetime.fromisoformat(raw)
            if utc.tzinfo is None:
                utc = utc.replace(tzinfo=pytz.UTC)
            else:
                utc = utc.astimezone(pytz.UTC)
        else:
            utc = datetime.fromisoformat(raw).replace(tzinfo=pytz.UTC)

        local_tz = pytz.timezone(tz_map.get(country, "Europe/Rome"))
        local = utc.astimezone(local_tz)

        # pytz handles BST/GMT transitions automatically for Europe/London —
        # no manual offset needed.

        return Fixture(
            id=fi["id"],
            date=local,
            status=fi["status"]["short"],
            home_team=Team(id=ti["home"]["id"], name=ti["home"]["name"], logo=ti["home"]["logo"]),
            away_team=Team(id=ti["away"]["id"], name=ti["away"]["name"], logo=ti["away"]["logo"]),
            venue=fi["venue"]["name"] if fi.get("venue") else None,
        )

    @staticmethod
    def _extract_round(fd: Dict[str, Any]) -> Optional[int]:
        round_info = fd.get("league", {}).get("round", "")
        for sep in ("- ", "Matchday "):
            if sep in round_info:
                try:
                    return int(round_info.split(sep)[-1])
                except ValueError:
                    pass
        return None

    # ── European competition filtering ────────────────────────────────────────

    def _filter_european_competition_teams(
        self, teams: List[Team], league_name: str
    ) -> List[Team]:
        if league_name == "Champions League":
            return self._filter_ucl_teams(teams)
        if league_name == "Europa League":
            return self._filter_uel_teams(teams)
        return teams

    def _filter_ucl_teams(self, teams: List[Team]) -> List[Team]:
        known = {
            "Arsenal", "Chelsea", "Liverpool", "Manchester City", "Manchester United",
            "Newcastle", "Real Madrid", "Barcelona", "Atletico Madrid", "Real Sociedad",
            "Athletic Bilbao", "Girona", "Inter", "Milan", "Juventus", "Atalanta",
            "Roma", "Napoli", "Bayern München", "Borussia Dortmund", "Bayer Leverkusen",
            "RB Leipzig", "Stuttgart", "Eintracht Frankfurt", "Paris Saint Germain",
            "Monaco", "Lille", "Lyon", "Marseille", "Brest", "PSV", "Ajax",
            "Feyenoord", "Benfica", "Porto", "Sporting CP", "Club Brugge", "Anderlecht",
        }
        filtered = [t for t in teams if t.name in known]
        return filtered if len(filtered) >= 36 else sorted(teams, key=lambda x: x.id)[:36]

    def _filter_uel_teams(self, teams: List[Team]) -> List[Team]:
        known = {
            "Tottenham", "Aston Villa", "Brighton", "West Ham", "Wolves",
            "Villarreal", "Real Betis", "Sevilla", "Valencia", "Osasuna",
            "Lazio", "Fiorentina", "Torino", "Bologna", "Genoa",
            "Union Berlin", "Borussia Mönchengladbach", "Wolfsburg", "Augsburg",
            "Hoffenheim", "Nice", "Lens", "Rennes", "Toulouse", "Nantes",
            "AZ Alkmaar", "FC Utrecht", "Twente", "Heerenveen", "Braga",
            "Vitoria Guimaraes", "Arouca", "Gil Vicente", "Gent", "Antwerp",
            "Standard Liege", "Genk", "Shakhtar Donetsk", "Dynamo Kyiv",
            "Red Bull Salzburg", "Rapid Vienna", "Olympiacos", "Panathinaikos",
            "AEK Athens", "Fenerbahce", "Galatasaray", "Besiktas",
            "Celtic", "Rangers", "Hearts",
        }
        filtered = [t for t in teams if t.name in known]
        return filtered if len(filtered) >= 36 else sorted(teams, key=lambda x: x.id)[:36]
