"""Roster service — fetches and caches squad / player data."""

import asyncio
from datetime import datetime
from typing import Any, Dict, List

from adapters.http_client import FootballHTTPClient


class RosterService:
    """
    Responsible for everything roster/player-related.

    Knows about squads, season stats per player, and the Redis cache
    layer for that data.  Nothing about fixtures or match odds.
    """

    def __init__(self, http: FootballHTTPClient, cache):
        self._http = http
        self._cache = cache

    # ── public ────────────────────────────────────────────────────────────────

    async def get_team_squad(
        self, team_id: int, season: int, auto_refresh: bool = True
    ) -> List[Dict]:
        cached = self._cache.get_team_roster(team_id, season)

        if cached and auto_refresh:
            from utils.roster_monitor import RosterMonitor
            monitor = RosterMonitor(self, self._cache)
            try:
                refreshed = await monitor.smart_roster_refresh(team_id, season, max_age_hours=24)
                if refreshed:
                    print(f"🔄 Auto-refreshed roster for team {team_id}")
                    cached = self._cache.get_team_roster(team_id, season)
                else:
                    print(f"📊 Using cached roster for team {team_id}")
            except Exception as exc:
                print(f"⚠️ Auto-refresh failed for team {team_id}: {exc}")
                print(f"📊 Using cached roster for team {team_id}")

        if cached:
            return cached

        return await self._get_hybrid(team_id, season)

    async def get_team_players(self, team_id: int, season: int) -> List[Dict]:
        try:
            return await self.get_team_squad(team_id, season, auto_refresh=True)
        except Exception as exc:
            print(f"❌ Error fetching team players: {exc}")
            return []

    async def get_team_roster_fast(self, team_id: int, season: int) -> List[Dict]:
        """Squad fetch without filtering — for utility menus."""
        try:
            data = await self._http.request("/players/squads", {"team": team_id})
            if data.get("response"):
                return data["response"][0].get("players", [])
        except Exception as exc:
            print(f"⚠️ Error fetching roster fast: {exc}")
        return []

    async def get_player_statistics(
        self, player_id: int, league_id: int, season: int
    ) -> Dict:
        cache_key = f"player_stats:{player_id}:{league_id}:{season}"
        cached = await self._cache.get_data(cache_key)
        if cached:
            print(f"📊 Using cached player stats for player {player_id}")
            return cached

        print(f"🔄 Fetching player stats for player {player_id} from API...")
        try:
            data = await self._http.request(
                "/players", {"player": player_id, "league": league_id, "season": season}
            )
            if data.get("response"):
                player_data = data["response"][0]
                stats = player_data.get("statistics", [])
                league_stats = next(
                    (s for s in stats if s.get("league", {}).get("id") == league_id), None
                ) or (stats[0] if stats else None)

                if league_stats:
                    result = {
                        "player_id": player_id,
                        "name": player_data["player"]["name"],
                        "position": player_data["player"]["position"],
                        "age": player_data["player"]["age"],
                        "nationality": player_data["player"]["nationality"],
                        "team_id": league_stats["team"]["id"],
                        "team_name": league_stats["team"]["name"],
                        "league_id": league_id,
                        "season": season,
                        "games": league_stats["games"],
                        "goals": league_stats["goals"],
                        "cards": league_stats["cards"],
                        "shots": league_stats["shots"],
                        "passes": league_stats["passes"],
                        "tackles": league_stats["tackles"],
                        "duels": league_stats["duels"],
                        "dribbles": league_stats["dribbles"],
                        "fouls": league_stats["fouls"],
                        "penalty": league_stats["penalty"],
                    }
                    await self._cache.set_data(cache_key, result, "historical_data")
                    print(f"✅ Fetched player stats for {player_data['player']['name']}")
                    return result
        except Exception as exc:
            print(f"❌ Error fetching player statistics: {exc}")

        print(f"⚠️ No statistics found for player {player_id} in league {league_id}")
        return {}

    async def force_update_roster(self, team_id: int, season: int) -> bool:
        print(f"🔄 Force updating roster for team {team_id}...")
        self._cache.delete_data(f"team_squad:{team_id}:{season}")
        try:
            players = await self.get_team_players(team_id, season)
            if players:
                update_key = f"roster_last_update:{team_id}:{season}"
                await self._cache.set_data(update_key, datetime.now().isoformat(), "roster")
                print(f"✅ Force updated roster for team {team_id} ({len(players)} players)")
                return True
            print(f"❌ Failed to update roster for team {team_id}")
            return False
        except Exception as exc:
            print(f"❌ Error force updating team roster: {exc}")
            return False

    async def force_update_player_statistics(
        self, player_id: int, league_id: int, season: int
    ) -> bool:
        print(f"🔄 Force updating player statistics for player {player_id}...")
        self._cache.delete_data(f"player_stats:{player_id}:{league_id}:{season}")
        try:
            stats = await self.get_player_statistics(player_id, league_id, season)
            if stats:
                print(f"✅ Force updated player statistics for player {player_id}")
                return True
            print(f"❌ Failed to update player statistics for player {player_id}")
            return False
        except Exception as exc:
            print(f"❌ Error force updating player statistics: {exc}")
            return False

    # ── squad fetching strategies ─────────────────────────────────────────────

    async def _get_hybrid(self, team_id: int, season: int) -> List[Dict]:
        """Hybrid: current squad + enrich with season stats."""
        try:
            print(f"🔄 Fetching roster for team {team_id} using hybrid approach...")
            current_squad = await self._get_current_squad(team_id)
            if not current_squad:
                print(f"⚠️ No current squad found, falling back to statistics method")
                return await self._get_direct(team_id, season)

            enriched = []
            for player in current_squad:
                pid = player.get("id")
                if not pid:
                    continue
                stats = await self._get_player_season_stats(pid, team_id, season)
                enriched.append({**player, **stats})

            active = [
                p for p in enriched
                if (p.get("appearances") or 0) > 0
                or (p.get("minutes") or 0) > 0
                or (p.get("appearances") is None and p.get("minutes") is None)
            ]
            inactive = len(enriched) - len(active)

            if active:
                self._cache.set_team_roster(team_id, season, active)
                print(f"✅ Cached hybrid roster for team {team_id} ({len(active)} players)")
                if inactive:
                    print(f"   🗑️ Filtered out {inactive} inactive players")

            return active

        except Exception as exc:
            print(f"⚠️ Error in hybrid squad fetch for team {team_id}: {exc}")
            return await self._get_direct(team_id, season)

    async def _get_current_squad(self, team_id: int) -> List[Dict]:
        try:
            data = await self._http.request("/players/squads", {"team": team_id})
            if not data.get("response"):
                return []
            squad_data = data["response"][0] if data["response"] else {}
            players = []
            for p in squad_data.get("players", []):
                players.append({
                    "id": p.get("id"), "name": p.get("name"),
                    "firstname": p.get("firstname"), "lastname": p.get("lastname"),
                    "age": p.get("age"), "nationality": p.get("nationality"),
                    "height": p.get("height"), "weight": p.get("weight"),
                    "position": p.get("position"), "number": p.get("number"),
                    "photo": p.get("photo"), "team_id": team_id,
                    "source": "current_squad",
                })
            print(f"✅ Found {len(players)} players in current squad")
            return players
        except Exception as exc:
            print(f"⚠️ Error fetching current squad: {exc}")
            return []

    async def _get_direct(self, team_id: int, season: int) -> List[Dict]:
        try:
            print(f"🔄 Fetching roster for team {team_id} using direct method...")
            data = await self._http.request("/players", {"team": team_id, "season": season})
            if data.get("response"):
                players = []
                for pd in data["response"]:
                    pi = pd.get("player", {})
                    cs = (pd.get("statistics") or [{}])[0]
                    games = cs.get("games", {})
                    cards = cs.get("cards", {})
                    fouls = cs.get("fouls", {})
                    players.append({
                        "id": pi.get("id"), "name": pi.get("name"),
                        "firstname": pi.get("firstname"), "lastname": pi.get("lastname"),
                        "age": pi.get("age"), "nationality": pi.get("nationality"),
                        "height": pi.get("height"), "weight": pi.get("weight"),
                        "position": games.get("position"),
                        "appearances": games.get("appearences", 0),
                        "minutes": games.get("minutes", 0),
                        "yellow_cards": cards.get("yellow", 0),
                        "red_cards": cards.get("red", 0),
                        "fouls_committed": fouls.get("committed", 0),
                        "fouls_drawn": fouls.get("drawn", 0),
                        "team_id": team_id,
                    })
                if players:
                    self._cache.set_team_roster(team_id, season, players)
                    print(f"✅ Cached roster for team {team_id} ({len(players)} players)")
                return players
        except Exception as exc:
            print(f"⚠️ Error fetching squad for team {team_id}: {exc}")
        return []

    async def _get_from_league(
        self, team_id: int, league_id: int, season: int
    ) -> List[Dict]:
        """Fetch roster from league-wide player data (accurate for big leagues)."""
        try:
            print(f"🔄 Fetching roster for team {team_id} from league data...")
            league_key = f"league:{league_id}:{season}:all_players"
            league_data = self._cache._get_with_decompression(league_key)
            if not league_data:
                print(f"🔄 Fetching all players for season {season}...")
                league_data = await self._fetch_all_league_players(league_id, season)
                self._cache._set_with_ttl(
                    league_key, league_data, "league_standings", compress=True
                )
                print(f"✅ Cached all players ({len(league_data)} players)")
            else:
                print(f"📊 Using cached player data ({len(league_data)} players)")

            players = []
            for pd in league_data:
                pi = pd.get("player", {})
                statistics = pd.get("statistics", [])
                if not statistics:
                    continue
                ts = statistics[0]
                ti = ts.get("team", {})
                if ti.get("id") != team_id:
                    continue
                games = ts.get("games", {})
                cards = ts.get("cards", {})
                fouls = ts.get("fouls", {})
                players.append({
                    "id": pi.get("id"), "name": pi.get("name"),
                    "firstname": pi.get("firstname"), "lastname": pi.get("lastname"),
                    "age": pi.get("age"), "nationality": pi.get("nationality"),
                    "height": pi.get("height"), "weight": pi.get("weight"),
                    "position": games.get("position"),
                    "appearances": games.get("appearences", 0),
                    "minutes": games.get("minutes", 0),
                    "yellow_cards": cards.get("yellow", 0),
                    "red_cards": cards.get("red", 0),
                    "fouls_committed": fouls.get("committed", 0),
                    "fouls_drawn": fouls.get("drawn", 0),
                    "team_id": team_id,
                    "team_name": ti.get("name"),
                })

            if players:
                self._cache.set_team_roster(team_id, season, players)
                print(f"✅ Cached roster for team {team_id} ({len(players)} players)")
            return players

        except Exception as exc:
            print(f"⚠️ Error fetching squad from league data for team {team_id}: {exc}")
            return await self._get_direct(team_id, season)

    async def _fetch_all_league_players(self, league_id: int, season: int) -> List[Dict]:
        all_players: List[Dict] = []
        page = 1
        while True:
            try:
                data = await self._http.request(
                    "/players", {"league": league_id, "season": season, "page": page}
                )
                if not data.get("response"):
                    break
                all_players.extend(data["response"])
                paging = data.get("paging", {})
                if paging.get("current", page) >= paging.get("total", 1):
                    break
                page += 1
                if page % 2 == 0:
                    await asyncio.sleep(1)
            except Exception as exc:
                print(f"⚠️ Error fetching league players page {page}: {exc}")
                break
        return all_players

    async def _get_player_season_stats(
        self, player_id: int, team_id: int, season: int
    ) -> Dict[str, Any]:
        try:
            data = await self._http.request(
                "/players", {"id": player_id, "season": season, "team": team_id}
            )
            if data.get("response"):
                player_data = data["response"][0]
                stats = player_data.get("statistics", [])
                team_stats = next(
                    (s for s in stats if s.get("team", {}).get("id") == team_id), None
                ) or (stats[0] if stats else None)

                if team_stats:
                    games = team_stats.get("games", {})
                    cards = team_stats.get("cards", {})
                    fouls = team_stats.get("fouls", {})
                    return {
                        "appearances": games.get("appearences", 0),
                        "minutes": games.get("minutes", 0),
                        "lineups": games.get("lineups", 0),
                        "rating": games.get("rating"),
                        "yellow_cards": cards.get("yellow", 0),
                        "red_cards": cards.get("red", 0),
                        "fouls_committed": fouls.get("committed", 0),
                        "fouls_drawn": fouls.get("drawn", 0),
                        "captain": games.get("captain", False),
                        "source": "season_stats",
                    }
        except Exception as exc:
            print(f"⚠️ Error fetching player {player_id} stats: {exc}")
        return {}
