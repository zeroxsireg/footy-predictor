"""Football API adapter for fetching match and team data."""

import httpx
from datetime import datetime, date
from typing import List, Dict, Any, Optional
import asyncio
import time
import pytz

from core.config import get_settings
from core.models import Team, Fixture, TeamStats


class FootballAPIError(Exception):
    """Exception raised for Football API errors."""
    pass


class FootballAPIClient:
    """Client for the Football API."""
    
    def __init__(self):
        self.settings = get_settings()
        self.base_url = self.settings.api_football_base
        self.headers = {
            "x-apisports-key": self.settings.api_football_key
        }
        self.last_request_time = 0
        self.min_request_interval = 1.0  # Minimum 1 second between requests
        
        # Cache for league IDs to avoid repeated API calls
        self._league_cache = {
            ("Italy", "Serie A"): 135,  # Serie A ID is well-known
            ("England", "Premier League"): 39,
            ("Spain", "La Liga"): 140,
            ("Germany", "Bundesliga"): 78,
            ("France", "Ligue 1"): 61,
            ("UEFA", "Champions League"): 2,  # Champions League
            ("UEFA", "Europa League"): 3      # Europa League
        }
        
        # Redis cache for team data and statistics
        from utils.redis_cache import get_redis_cache
        self.redis_cache = get_redis_cache()
    
    async def _make_request(self, endpoint: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Make an API request with rate limiting."""
        # Rate limiting: ensure minimum interval between requests
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.min_request_interval:
            await asyncio.sleep(self.min_request_interval - time_since_last)
        
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        async with httpx.AsyncClient() as client:
            try:
                self.last_request_time = time.time()
                response = await client.get(url, headers=self.headers, params=params or {})
                response.raise_for_status()
                data = response.json()
                
                # Check for API errors
                if "errors" in data and data["errors"]:
                    if "rateLimit" in data["errors"]:
                        raise FootballAPIError(f"Rate limit exceeded: {data['errors']['rateLimit']}")
                    else:
                        raise FootballAPIError(f"API errors: {data['errors']}")
                
                return data
            except httpx.HTTPError as e:
                raise FootballAPIError(f"API request failed: {e}")
    
    async def get_league_id(self, country: str = None, league_name: str = None, season: int = None) -> int:
        """Get league ID by country and league name."""
        country = country or self.settings.default_country
        league_name = league_name or self.settings.default_league
        season = season or self.settings.default_season
        
        # Check cache first for major leagues
        cache_key = (country, league_name)
        if cache_key in self._league_cache:
            return self._league_cache[cache_key]
        
        # Special handling for UEFA competitions
        if country == "UEFA":
            if league_name == "Champions League":
                return 2
            elif league_name == "Europa League":
                return 3
            else:
                raise FootballAPIError(f"UEFA competition not supported: {league_name}")
        
        # If not in cache, make API call
        params = {
            "country": country,
            "name": league_name,
            "season": season
        }
        
        data = await self._make_request("/leagues", params)
        
        if not data["response"]:
            raise FootballAPIError(f"League not found: {league_name} in {country}")
        
        league_id = data["response"][0]["league"]["id"]
        
        # Cache the result for future use
        self._league_cache[cache_key] = league_id
        
        return league_id
    
    async def get_league_standings(self, league_id: int, season: int) -> Optional[List[Dict]]:
        """Get current league standings."""
        try:
            params = {
                "league": league_id,
                "season": season
            }
            
            data = await self._make_request("/standings", params)
            
            if data.get("response") and len(data["response"]) > 0:
                standings = data["response"][0].get("league", {}).get("standings", [])
                if standings:
                    return standings[0]  # Return the first group (usually the main league standings)
            
            return None
            
        except Exception as e:
            print(f"⚠️ Error fetching league standings: {e}")
            return None
    
    async def get_next_round_fixtures(self, league_id: int = None, season: int = None, country: str = None) -> tuple[List[Fixture], int]:
        """Get fixtures for the next round of matches."""
        if league_id is None:
            league_id = await self.get_league_id()
        
        season = season or self.settings.default_season
        
        # Get next fixtures (upcoming matches)
        params = {
            "league": league_id,
            "season": season,
            "next": "15"  # Get next 15 matches to cover full matchday
        }
        
        data = await self._make_request("/fixtures", params)
        
        # If no upcoming matches, try to get recent matches
        if not data.get("response"):
            params = {
                "league": league_id,
                "season": season,
                "last": "15"  # Get last 15 matches to cover full matchday
            }
            data = await self._make_request("/fixtures", params)
        
        if not data.get("response"):
            raise FootballAPIError(f"No fixtures found for league {league_id} season {season}")
        
        fixtures = []
        country = country or self.settings.default_country
        next_round = None
        
        for fixture_data in data["response"]:
            fixture = self._parse_fixture(fixture_data, country)
            fixtures.append(fixture)
        
            # Get the round number from the first fixture
            if next_round is None:
                round_info = fixture_data.get("league", {}).get("round", "")
                # Extract round number from strings like "Regular Season - 8" or "Matchday 8"
                if "- " in round_info:
                    try:
                        next_round = int(round_info.split("- ")[-1])
                    except ValueError:
                        next_round = 1
                elif "Matchday" in round_info:
                    try:
                        next_round = int(round_info.split("Matchday ")[-1])
                    except ValueError:
                        next_round = 1
                else:
                    next_round = 1
        
        # Filter fixtures to only include those from the same round
        if next_round and len(fixtures) > 10:  # If we have more than 10 matches, filter by round
            filtered_fixtures = []
            for fixture_data in data["response"]:
                round_info = fixture_data.get("league", {}).get("round", "")
                fixture_round = None
                
                if "- " in round_info:
                    try:
                        fixture_round = int(round_info.split("- ")[-1])
                    except ValueError:
                        fixture_round = next_round
                elif "Matchday" in round_info:
                    try:
                        fixture_round = int(round_info.split("Matchday ")[-1])
                    except ValueError:
                        fixture_round = next_round
                else:
                    fixture_round = next_round
                
                # Only include fixtures from the next round
                if fixture_round == next_round:
                    fixture = self._parse_fixture(fixture_data, country)
                    filtered_fixtures.append(fixture)
            
            if filtered_fixtures:
                fixtures = filtered_fixtures
        
        return fixtures, next_round or 1
    
    async def get_team_statistics(self, team_id: int, league_id: int = None, season: int = None) -> TeamStats:
        """Get team statistics for a season with Redis caching."""
        if league_id is None:
            league_id = await self.get_league_id()
        
        season = season or self.settings.default_season
        
        # Check Redis cache first
        cached_stats = self.redis_cache.get_team_stats(team_id, league_id, season)
        if cached_stats:
            print(f"📊 Using cached team stats for team {team_id}")
            # Reconstruct TeamStats object from cached data (includes shots/corners)
            from core.models import Team
            team = Team(
                id=cached_stats["team"]["id"],
                name=cached_stats["team"]["name"],
                logo=cached_stats["team"]["logo"]
            )
            
            team_stats = TeamStats(
                team=team,
                matches_played=cached_stats["matches_played"],
                wins=cached_stats["wins"],
                draws=cached_stats["draws"],
                losses=cached_stats["losses"],
                goals_for=cached_stats["goals_for"],
                goals_against=cached_stats["goals_against"],
                shots_total=cached_stats["shots_total"],
                shots_on_target=cached_stats["shots_on_target"],
                corners=cached_stats["corners"],
                yellow_cards=cached_stats["yellow_cards"],
                red_cards=cached_stats["red_cards"],
                form=cached_stats.get("form", ""),
                clean_sheets=cached_stats.get("clean_sheets", 0),
                failed_to_score=cached_stats.get("failed_to_score", 0),
                penalties_scored=cached_stats.get("penalties_scored", 0),
                penalties_missed=cached_stats.get("penalties_missed", 0),
                biggest_win_margin=cached_stats.get("biggest_win_margin", 0),
                biggest_loss_margin=cached_stats.get("biggest_loss_margin", 0),
                over_1_5_goals=cached_stats.get("over_1_5_goals", 0),
                over_2_5_goals=cached_stats.get("over_2_5_goals", 0),
                over_3_5_goals=cached_stats.get("over_3_5_goals", 0),
                over_1_5_conceded=cached_stats.get("over_1_5_conceded", 0),
                over_2_5_conceded=cached_stats.get("over_2_5_conceded", 0),
                over_3_5_conceded=cached_stats.get("over_3_5_conceded", 0)
            )
            return team_stats
        
        print(f"🔄 Fetching fresh team stats for team {team_id} from API...")
        
        params = {
            "team": team_id,
            "league": league_id,
            "season": season
        }
        
        data = await self._make_request("/teams/statistics", params)
        
        # If no data for current season, try previous season
        if not data.get("response") and season >= 2024:
            params["season"] = season - 1
            data = await self._make_request("/teams/statistics", params)
        
        if not data.get("response"):
            raise FootballAPIError(f"No statistics found for team {team_id} in seasons {season} or {season-1}")
        
        team_stats = self._parse_team_statistics(data["response"])
        
        # Get shots and corners from recent matches (only when fetching fresh data)
        shots_corners_data = await self._get_team_shots_corners(team_id, league_id, season)
        team_stats.shots_total = shots_corners_data["shots_total"]
        team_stats.shots_on_target = shots_corners_data["shots_on_target"] 
        team_stats.corners = shots_corners_data["corners"]
        
        # Cache the team stats in Redis
        stats_dict = {
            "team": {
                "id": team_stats.team.id,
                "name": team_stats.team.name,
                "logo": team_stats.team.logo
            },
            "matches_played": team_stats.matches_played,
            "wins": team_stats.wins,
            "draws": team_stats.draws,
            "losses": team_stats.losses,
            "goals_for": team_stats.goals_for,
            "goals_against": team_stats.goals_against,
            "shots_total": team_stats.shots_total,
            "shots_on_target": team_stats.shots_on_target,
            "corners": team_stats.corners,
            "yellow_cards": team_stats.yellow_cards,
            "red_cards": team_stats.red_cards,
            "form": team_stats.form,
            "clean_sheets": team_stats.clean_sheets,
            "failed_to_score": team_stats.failed_to_score,
            "penalties_scored": team_stats.penalties_scored,
            "penalties_missed": team_stats.penalties_missed,
            "biggest_win_margin": team_stats.biggest_win_margin,
            "biggest_loss_margin": team_stats.biggest_loss_margin,
            "over_1_5_goals": team_stats.over_1_5_goals,
            "over_2_5_goals": team_stats.over_2_5_goals,
            "over_3_5_goals": team_stats.over_3_5_goals,
            "over_1_5_conceded": team_stats.over_1_5_conceded,
            "over_2_5_conceded": team_stats.over_2_5_conceded,
            "over_3_5_conceded": team_stats.over_3_5_conceded
        }
        
        self.redis_cache.set_team_stats(team_id, league_id, season, stats_dict)
        print(f"✅ Cached team stats for team {team_id}")
        
        return team_stats
    
    async def _get_team_shots_corners(self, team_id: int, league_id: int, season: int) -> Dict[str, int]:
        """Get shots and corners statistics with Redis caching."""
        # Check Redis cache first
        cached_stats = self.redis_cache.get_team_shots_corners(team_id, season)
        if cached_stats and cached_stats.get("matches_processed", 0) > 0:
            print(f"📊 Using cached shots/corners for team {team_id}")
            return {
                "shots_total": cached_stats["shots_total"],
                "shots_on_target": cached_stats["shots_on_target"],
                "corners": cached_stats["corners"]
            }
        
        print(f"🔄 Calculating shots/corners for team {team_id} from all season matches...")
        
        # Get ALL matches for the team in the season
        params = {
            "team": team_id,
            "league": league_id,
            "season": season
        }
        
        try:
            data = await self._make_request("/fixtures", params)
            
            if not data.get("response"):
                result = {"shots_total": 0, "shots_on_target": 0, "corners": 0}
                self.redis_cache.set_team_shots_corners(team_id, season, {
                    **result, "matches_processed": 0
                })
                return result
            
            total_shots = 0
            total_shots_on_target = 0
            total_corners = 0
            matches_processed = 0
            processed_matches = set()
            
            # Get existing processed matches from cache
            existing_stats = cached_stats or {}
            if existing_stats.get("processed_matches"):
                processed_matches = set(existing_stats["processed_matches"])
                total_shots = existing_stats.get("shots_total", 0)
                total_shots_on_target = existing_stats.get("shots_on_target", 0)
                total_corners = existing_stats.get("corners", 0)
                matches_processed = existing_stats.get("matches_processed", 0)
            
            new_matches = 0
            for fixture in data["response"]:
                match_id = fixture["fixture"]["id"]
                
                # Only process finished matches
                if fixture["fixture"]["status"]["short"] != "FT":
                    continue
                
                # Skip if already processed
                if match_id in processed_matches:
                    continue
                
                new_matches += 1
                
                # Get detailed match statistics
                match_data = await self._get_match_statistics(match_id, team_id)
                if match_data:
                    total_shots += match_data["shots"]
                    total_shots_on_target += match_data["shots_on_target"]
                    total_corners += match_data["corners"]
                    processed_matches.add(match_id)
                    matches_processed += 1
            
            # Save to Redis cache
            result = {
                "shots_total": total_shots,
                "shots_on_target": total_shots_on_target,
                "corners": total_corners,
                "matches_processed": matches_processed,
                "processed_matches": list(processed_matches)
            }
            
            self.redis_cache.set_team_shots_corners(team_id, season, result)
            
            if new_matches > 0:
                print(f"✅ Processed {new_matches} new matches for team {team_id}")
            
            return {
                "shots_total": total_shots,
                "shots_on_target": total_shots_on_target,
                "corners": total_corners
            }
            
        except Exception as e:
            print(f"⚠️ Warning: Could not fetch shots/corners for team {team_id}: {e}")
            result = {"shots_total": 0, "shots_on_target": 0, "corners": 0}
            return result
    
    async def _get_match_statistics(self, match_id: int, team_id: int) -> Optional[Dict[str, int]]:
        """Get detailed statistics for a specific match and team."""
        try:
            params = {"fixture": match_id}
            data = await self._make_request("/fixtures/statistics", params)
            
            if not data.get("response"):
                return None
            
            # Find statistics for the specific team
            for team_stats in data["response"]:
                if team_stats["team"]["id"] == team_id:
                    stats_dict = {}
                    for stat in team_stats["statistics"]:
                        stats_dict[stat["type"]] = stat["value"]
                    
                    return {
                        "shots": int(stats_dict.get("Total Shots", 0) or 0),
                        "shots_on_target": int(stats_dict.get("Shots on Goal", 0) or 0),
                        "corners": int(stats_dict.get("Corner Kicks", 0) or 0)
                    }
            
            return None
            
        except Exception as e:
            print(f"⚠️ Warning: Could not fetch match statistics for match {match_id}: {e}")
            return None
    
    def _parse_fixture(self, fixture_data: Dict[str, Any], country: str = "Italy") -> Fixture:
        """Parse fixture data from API response."""
        fixture_info = fixture_data["fixture"]
        teams = fixture_data["teams"]
        
        home_team = Team(
            id=teams["home"]["id"],
            name=teams["home"]["name"],
            logo=teams["home"]["logo"]
        )
        
        away_team = Team(
            id=teams["away"]["id"],
            name=teams["away"]["name"],
            logo=teams["away"]["logo"]
        )
        
        # Parse date and convert to local timezone
        raw_date = fixture_info["date"]
        
        # Handle different date formats from API
        if raw_date.endswith("Z"):
            # UTC format with Z
            utc_date = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
        elif "+" in raw_date or raw_date.count("-") > 2:
            # Already has timezone info
            utc_date = datetime.fromisoformat(raw_date)
            if utc_date.tzinfo is None:
                utc_date = utc_date.replace(tzinfo=pytz.UTC)
            else:
                # Convert to UTC first
                utc_date = utc_date.astimezone(pytz.UTC)
        else:
            # Assume UTC if no timezone info
            utc_date = datetime.fromisoformat(raw_date).replace(tzinfo=pytz.UTC)
        
        # Determine timezone based on country
        timezone_map = {
            "Italy": "Europe/Rome",
            "England": "Europe/London", 
            "Spain": "Europe/Madrid",
            "Germany": "Europe/Berlin",
            "France": "Europe/Paris",
            "Netherlands": "Europe/Amsterdam",
            "Portugal": "Europe/Lisbon",
            "Brazil": "America/Sao_Paulo"
        }
        
        # Use the country parameter to determine timezone
        local_tz_name = timezone_map.get(country, "Europe/Rome")
        local_tz = pytz.timezone(local_tz_name)
        local_date = utc_date.astimezone(local_tz)
        
        # TEMPORARY FIX: Add 1 hour for England matches (API seems to have timezone issue)
        if country == "England":
            from datetime import timedelta
            local_date = local_date + timedelta(hours=1)
        
        return Fixture(
            id=fixture_info["id"],
            date=local_date,
            status=fixture_info["status"]["short"],
            home_team=home_team,
            away_team=away_team,
            venue=fixture_info["venue"]["name"] if fixture_info["venue"] else None
        )
    
    def _parse_team_statistics(self, stats_data: Dict[str, Any]) -> TeamStats:
        """Parse team statistics from API response."""
        team_info = stats_data["team"]
        fixtures = stats_data["fixtures"]
        goals = stats_data["goals"]
        
        team = Team(
            id=team_info["id"],
            name=team_info["name"],
            logo=team_info["logo"]
        )
        
        # Extract statistics safely
        def safe_get(data, *keys, default=0):
            """Safely get nested dictionary values."""
            try:
                result = data
                for key in keys:
                    result = result[key]
                return result if result is not None else default
            except (KeyError, TypeError):
                return default
        
        # Calculate total yellow and red cards from minute breakdown
        yellow_total = 0
        red_total = 0
        
        if "cards" in stats_data:
            # Sum yellow cards from all time periods
            if "yellow" in stats_data["cards"]:
                for period, data in stats_data["cards"]["yellow"].items():
                    if data and data.get("total"):
                        yellow_total += data["total"]
            
            # Sum red cards from all time periods  
            if "red" in stats_data["cards"]:
                for period, data in stats_data["cards"]["red"].items():
                    if data and data.get("total"):
                        red_total += data["total"]
        
        # Extract additional statistics
        form = safe_get(stats_data, "form", default="")
        clean_sheets = safe_get(stats_data, "clean_sheet", "total", default=0)
        failed_to_score = safe_get(stats_data, "failed_to_score", "total", default=0)
        penalties_scored = safe_get(stats_data, "penalty", "scored", "total", default=0)
        penalties_missed = safe_get(stats_data, "penalty", "missed", "total", default=0)
        
        # Extract Under/Over statistics for goals scored
        over_1_5_goals = safe_get(stats_data, "goals", "for", "under_over", "1.5", "over", default=0)
        over_2_5_goals = safe_get(stats_data, "goals", "for", "under_over", "2.5", "over", default=0)
        over_3_5_goals = safe_get(stats_data, "goals", "for", "under_over", "3.5", "over", default=0)
        
        # Extract Under/Over statistics for goals conceded
        over_1_5_conceded = safe_get(stats_data, "goals", "against", "under_over", "1.5", "over", default=0)
        over_2_5_conceded = safe_get(stats_data, "goals", "against", "under_over", "2.5", "over", default=0)
        over_3_5_conceded = safe_get(stats_data, "goals", "against", "under_over", "3.5", "over", default=0)
        
        # Calculate biggest win/loss margins
        biggest_win_home = safe_get(stats_data, "biggest", "wins", "home", default="0-0")
        biggest_win_away = safe_get(stats_data, "biggest", "wins", "away", default="0-0")
        biggest_loss_home = safe_get(stats_data, "biggest", "loses", "home", default="0-0")
        biggest_loss_away = safe_get(stats_data, "biggest", "loses", "away", default="0-0")
        
        def parse_score_margin(score_str):
            """Parse score string like '3-1' to get goal margin."""
            try:
                if isinstance(score_str, str) and '-' in score_str:
                    goals = score_str.split('-')
                    return abs(int(goals[0]) - int(goals[1]))
                return 0
            except (ValueError, IndexError):
                return 0
        
        biggest_win_margin = max(
            parse_score_margin(biggest_win_home),
            parse_score_margin(biggest_win_away)
        )
        
        biggest_loss_margin = max(
            parse_score_margin(biggest_loss_home),
            parse_score_margin(biggest_loss_away)
        )
        
        return TeamStats(
            team=team,
            matches_played=safe_get(fixtures, "played", "total"),
            wins=safe_get(fixtures, "wins", "total"),
            draws=safe_get(fixtures, "draws", "total"),
            losses=safe_get(fixtures, "loses", "total"),
            goals_for=safe_get(goals, "for", "total", "total"),
            goals_against=safe_get(goals, "against", "total", "total"),
            shots_total=0,  # Will be filled by _get_team_shots_corners
            shots_on_target=0,  # Will be filled by _get_team_shots_corners
            corners=0,  # Will be filled by _get_team_shots_corners
            yellow_cards=yellow_total,
            red_cards=red_total,
            # Additional statistics
            form=form,
            clean_sheets=clean_sheets,
            failed_to_score=failed_to_score,
            penalties_scored=penalties_scored,
            penalties_missed=penalties_missed,
            biggest_win_margin=biggest_win_margin,
            biggest_loss_margin=biggest_loss_margin,
            # Under/Over statistics
            over_1_5_goals=over_1_5_goals,
            over_2_5_goals=over_2_5_goals,
            over_3_5_goals=over_3_5_goals,
            over_1_5_conceded=over_1_5_conceded,
            over_2_5_conceded=over_2_5_conceded,
            over_3_5_conceded=over_3_5_conceded
        )
    
    async def get_team_squad(self, team_id: int, season: int, auto_refresh: bool = True) -> List[Dict[str, Any]]:
        """Get current squad (players) for a team in a specific season with Redis caching and auto-refresh."""
        # Check Redis cache first
        cached_roster = self.redis_cache.get_team_roster(team_id, season)
        
        if cached_roster and auto_refresh:
            # Check if roster might need updating (smart refresh)
            from utils.roster_monitor import RosterMonitor
            monitor = RosterMonitor(self, self.redis_cache)
            
            try:
                # Smart refresh: check every 24 hours
                refreshed = await monitor.smart_roster_refresh(team_id, season, max_age_hours=24)
                if refreshed:
                    print(f"🔄 Auto-refreshed roster for team {team_id}")
                    # Get the updated roster
                    cached_roster = self.redis_cache.get_team_roster(team_id, season)
                else:
                    print(f"📊 Using cached roster for team {team_id}")
            except Exception as e:
                print(f"⚠️ Auto-refresh failed for team {team_id}: {e}")
                print(f"📊 Using cached roster for team {team_id}")
        
        if cached_roster:
            return cached_roster
        
        # No cache or auto_refresh disabled, fetch fresh data
        return await self._get_team_squad_hybrid(team_id, season)
    
    async def _get_team_squad_from_league(self, team_id: int, league_id: int, season: int) -> List[Dict[str, Any]]:
        """Get team squad from league-wide player data (more accurate for Serie A)."""
        try:
            print(f"🔄 Fetching roster for team {team_id} from league data...")
            
            # Check if we have league-wide data cached
            league_cache_key = f"league:{league_id}:{season}:all_players"
            cached_league_data = self.redis_cache._get_with_decompression(league_cache_key)
            
            if not cached_league_data:
                print(f"🔄 Fetching all Serie A players for season {season}...")
                cached_league_data = await self._fetch_all_league_players(league_id, season)
                
                # Cache league data for 24 hours
                self.redis_cache._set_with_ttl(league_cache_key, cached_league_data, 'league_standings', compress=True)
                print(f"✅ Cached all Serie A players ({len(cached_league_data)} players)")
            else:
                print(f"📊 Using cached Serie A player data ({len(cached_league_data)} players)")
            
            # Extract players for specific team
            team_players = []
            for player_data in cached_league_data:
                player_info = player_data.get("player", {})
                statistics = player_data.get("statistics", [])
                
                if not statistics:
                    continue
                    
                # Get team from statistics
                team_stats = statistics[0]
                team_info = team_stats.get("team", {})
                
                if team_info.get("id") == team_id:
                    player = {
                        "id": player_info.get("id"),
                        "name": player_info.get("name"),
                        "firstname": player_info.get("firstname"),
                        "lastname": player_info.get("lastname"),
                        "age": player_info.get("age"),
                        "nationality": player_info.get("nationality"),
                        "height": player_info.get("height"),
                        "weight": player_info.get("weight"),
                        "position": team_stats.get("games", {}).get("position"),
                        "appearances": team_stats.get("games", {}).get("appearences", 0),
                        "minutes": team_stats.get("games", {}).get("minutes", 0),
                        "yellow_cards": team_stats.get("cards", {}).get("yellow", 0),
                        "red_cards": team_stats.get("cards", {}).get("red", 0),
                        "fouls_committed": team_stats.get("fouls", {}).get("committed", 0),
                        "fouls_drawn": team_stats.get("fouls", {}).get("drawn", 0),
                        "team_id": team_id,
                        "team_name": team_info.get("name")
                    }
                    team_players.append(player)
            
            # Cache the team roster
            if team_players:
                self.redis_cache.set_team_roster(team_id, season, team_players)
                print(f"✅ Cached roster for team {team_id} ({len(team_players)} players)")
            
            return team_players
            
        except Exception as e:
            print(f"⚠️ Error fetching squad from league data for team {team_id}: {e}")
            # Fallback to direct method
            return await self._get_team_squad_direct(team_id, season)
    
    async def _fetch_all_league_players(self, league_id: int, season: int) -> List[Dict[str, Any]]:
        """Fetch all players from a league using pagination."""
        all_players = []
        page = 1
        
        while True:
            try:
                params = {
                    "league": league_id,
                    "season": season,
                    "page": page
                }
                
                data = await self._make_request("/players", params)
                
                if not data.get("response"):
                    break
                
                # Add players from this page
                page_players = data["response"]
                all_players.extend(page_players)
                
                # Check if there are more pages
                paging = data.get("paging", {})
                current_page = paging.get("current", page)
                total_pages = paging.get("total", 1)
                
                if current_page >= total_pages:
                    break
                    
                page += 1
                
                # Rate limiting - pause every 2 requests
                if page % 2 == 0:
                    await asyncio.sleep(1)
                    
            except Exception as e:
                print(f"⚠️ Error fetching league players page {page}: {e}")
                break
        
        return all_players
    
    async def _get_team_squad_direct(self, team_id: int, season: int) -> List[Dict[str, Any]]:
        """Get team squad using direct team endpoint (fallback method)."""
        try:
            print(f"🔄 Fetching roster for team {team_id} using direct method...")
            
            # API endpoint: /players?team=TEAM_ID&season=SEASON
            params = {
                "team": team_id,
                "season": season
            }
            
            data = await self._make_request("/players", params)
            
            if data.get("response"):
                players = []
                for player_data in data["response"]:
                    player_info = player_data.get("player", {})
                    statistics = player_data.get("statistics", [])
                    
                    # Get the most recent statistics (usually first in list)
                    current_stats = statistics[0] if statistics else {}
                    
                    player = {
                        "id": player_info.get("id"),
                        "name": player_info.get("name"),
                        "firstname": player_info.get("firstname"),
                        "lastname": player_info.get("lastname"),
                        "age": player_info.get("age"),
                        "nationality": player_info.get("nationality"),
                        "height": player_info.get("height"),
                        "weight": player_info.get("weight"),
                        "position": current_stats.get("games", {}).get("position"),
                        "appearances": current_stats.get("games", {}).get("appearences", 0),
                        "minutes": current_stats.get("games", {}).get("minutes", 0),
                        "yellow_cards": current_stats.get("cards", {}).get("yellow", 0),
                        "red_cards": current_stats.get("cards", {}).get("red", 0),
                        "fouls_committed": current_stats.get("fouls", {}).get("committed", 0),
                        "fouls_drawn": current_stats.get("fouls", {}).get("drawn", 0),
                        "team_id": team_id  # Add team_id for reference
                    }
                    
                    players.append(player)
                
                # Cache the roster in Redis
                if players:
                    self.redis_cache.set_team_roster(team_id, season, players)
                    print(f"✅ Cached roster for team {team_id} ({len(players)} players)")
                
                return players
            
            return []
            
        except Exception as e:
            print(f"⚠️ Error fetching squad for team {team_id}: {e}")
            return []
    
    async def _get_team_squad_hybrid(self, team_id: int, season: int) -> List[Dict[str, Any]]:
        """Get team squad using hybrid approach: squads endpoint + statistics validation."""
        try:
            print(f"🔄 Fetching roster for team {team_id} using hybrid approach...")
            
            # STEP 1: Get current squad from /players/squads (most accurate for current roster)
            current_squad = await self._get_current_squad(team_id)
            
            if not current_squad:
                print(f"⚠️ No current squad found, falling back to statistics method")
                return await self._get_team_squad_direct(team_id, season)
            
            # STEP 2: Enrich with statistics from /players endpoint
            enriched_players = []
            
            for player in current_squad:
                player_id = player.get("id")
                if not player_id:
                    continue
                
                # Get player statistics for the season
                player_stats = await self._get_player_season_stats(player_id, team_id, season)
                
                # Merge squad data with statistics
                enriched_player = {
                    **player,  # Basic info from squad
                    **player_stats  # Statistics from season
                }
                
                enriched_players.append(enriched_player)
            
            # Filter out inactive players (0 appearances and 0 minutes)
            active_players = []
            inactive_count = 0
            
            for player in enriched_players:
                appearances = player.get('appearances', 0) or 0
                minutes = player.get('minutes', 0) or 0
                
                # Keep players with game time OR if we can't determine activity
                if appearances > 0 or minutes > 0 or (appearances is None and minutes is None):
                    active_players.append(player)
                else:
                    inactive_count += 1
            
            # Cache the filtered roster
            if active_players:
                self.redis_cache.set_team_roster(team_id, season, active_players)
                print(f"✅ Cached hybrid roster for team {team_id} ({len(active_players)} players)")
                if inactive_count > 0:
                    print(f"   🗑️ Filtered out {inactive_count} inactive players")
            
            return active_players
            
        except Exception as e:
            print(f"⚠️ Error in hybrid squad fetch for team {team_id}: {e}")
            # Fallback to direct method
            return await self._get_team_squad_direct(team_id, season)
    
    async def _get_current_squad(self, team_id: int) -> List[Dict[str, Any]]:
        """Get current squad using /players/squads endpoint."""
        try:
            params = {"team": team_id}
            data = await self._make_request("/players/squads", params)
            
            if not data.get("response"):
                return []
            
            # Extract players from squad response
            squad_data = data["response"][0] if data["response"] else {}
            players_data = squad_data.get("players", [])
            
            players = []
            for player_data in players_data:
                player = {
                    "id": player_data.get("id"),
                    "name": player_data.get("name"),
                    "firstname": player_data.get("firstname"),
                    "lastname": player_data.get("lastname"),
                    "age": player_data.get("age"),
                    "nationality": player_data.get("nationality"),
                    "height": player_data.get("height"),
                    "weight": player_data.get("weight"),
                    "position": player_data.get("position"),
                    "number": player_data.get("number"),
                    "photo": player_data.get("photo"),
                    "team_id": team_id,
                    "source": "current_squad"  # Mark source
                }
                players.append(player)
            
            print(f"✅ Found {len(players)} players in current squad")
            return players
            
        except Exception as e:
            print(f"⚠️ Error fetching current squad: {e}")
            return []
    
    async def _get_player_season_stats(self, player_id: int, team_id: int, season: int) -> Dict[str, Any]:
        """Get player statistics for a specific season."""
        try:
            params = {
                "id": player_id,
                "season": season,
                "team": team_id
            }
            
            data = await self._make_request("/players", params)
            
            if not data.get("response"):
                return {}
            
            player_data = data["response"][0] if data["response"] else {}
            statistics = player_data.get("statistics", [])
            
            if not statistics:
                return {}
            
            # Get statistics for the specific team/season
            team_stats = None
            for stat in statistics:
                if stat.get("team", {}).get("id") == team_id:
                    team_stats = stat
                    break
            
            if not team_stats:
                team_stats = statistics[0]  # Fallback to first stats
            
            # Extract relevant statistics
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
                "source": "season_stats"  # Mark source
            }
            
        except Exception as e:
            print(f"⚠️ Error fetching player {player_id} stats: {e}")
            return {}
    
    async def get_live_fixtures(self, leagues: List[int] = None) -> List[Dict[str, Any]]:
        """Get live fixtures from specified leagues or all leagues."""
        try:
            params = {"live": "all"}
            
            data = await self._make_request("/fixtures", params)
            
            if data.get("response"):
                live_fixtures = []
                
                from datetime import datetime, timezone, timedelta
                today = datetime.now(timezone.utc).date()
                
                for fixture_data in data["response"]:
                    fixture_info = fixture_data.get("fixture", {})
                    league_info = fixture_data.get("league", {})
                    teams_info = fixture_data.get("teams", {})
                    score_info = fixture_data.get("score", {})
                    
                    # Parse fixture date
                    fixture_date_str = fixture_info.get("date", "")
                    try:
                        fixture_date = datetime.fromisoformat(fixture_date_str.replace('Z', '+00:00')).date()
                    except:
                        fixture_date = None
                    
                    # Filter by date - only today's matches
                    if fixture_date != today:
                        continue
                    
                    # Filter by leagues if specified
                    if leagues and league_info.get("id") not in leagues:
                        continue
                    
                    fixture = {
                        "id": fixture_info.get("id"),
                        "date": fixture_info.get("date"),
                        "status": fixture_info.get("status", {}).get("short"),
                        "elapsed": fixture_info.get("status", {}).get("elapsed"),
                        "venue": fixture_info.get("venue", {}).get("name"),
                        "league": {
                            "id": league_info.get("id"),
                            "name": league_info.get("name"),
                            "country": league_info.get("country"),
                            "flag": league_info.get("flag"),
                            "logo": league_info.get("logo")
                        },
                        "home_team": {
                            "id": teams_info.get("home", {}).get("id"),
                            "name": teams_info.get("home", {}).get("name"),
                            "logo": teams_info.get("home", {}).get("logo")
                        },
                        "away_team": {
                            "id": teams_info.get("away", {}).get("id"),
                            "name": teams_info.get("away", {}).get("name"),
                            "logo": teams_info.get("away", {}).get("logo")
                        },
                        "score": {
                            "home": score_info.get("fulltime", {}).get("home"),
                            "away": score_info.get("fulltime", {}).get("away"),
                            "halftime_home": score_info.get("halftime", {}).get("home"),
                            "halftime_away": score_info.get("halftime", {}).get("away")
                        }
                    }
                    
                    live_fixtures.append(fixture)
                
                return live_fixtures
            
            return []
            
        except Exception as e:
            print(f"⚠️ Error fetching live fixtures: {e}")
            return []
    
    async def get_live_match_statistics(self, fixture_id: int) -> Dict[str, Any]:
        """Get live match statistics for a specific fixture."""
        try:
            params = {"fixture": fixture_id}
            
            data = await self._make_request("/fixtures/statistics", params)
            
            if data.get("response"):
                stats_data = data["response"]
                
                # Parse statistics for both teams
                live_stats = {
                    "home": {},
                    "away": {}
                }
                
                for team_stats in stats_data:
                    team_name = team_stats.get("team", {}).get("name", "")
                    is_home = team_stats.get("team", {}).get("id") == stats_data[0].get("team", {}).get("id")
                    team_key = "home" if is_home else "away"
                    
                    statistics = team_stats.get("statistics", [])
                    
                    for stat in statistics:
                        stat_type = stat.get("type", "")
                        stat_value = stat.get("value")
                        
                        # Convert percentage strings to numbers
                        if isinstance(stat_value, str) and "%" in stat_value:
                            try:
                                stat_value = float(stat_value.replace("%", ""))
                            except:
                                stat_value = 0
                        
                        # Map important statistics
                        if stat_type == "Shots on Goal":
                            live_stats[team_key]["shots_on_target"] = stat_value or 0
                        elif stat_type == "Total Shots":
                            live_stats[team_key]["total_shots"] = stat_value or 0
                        elif stat_type == "Ball Possession":
                            live_stats[team_key]["possession"] = stat_value or 0
                        elif stat_type == "Corner Kicks":
                            live_stats[team_key]["corners"] = stat_value or 0
                        elif stat_type == "Offsides":
                            live_stats[team_key]["offsides"] = stat_value or 0
                        elif stat_type == "Yellow Cards":
                            live_stats[team_key]["yellow_cards"] = stat_value or 0
                        elif stat_type == "Red Cards":
                            live_stats[team_key]["red_cards"] = stat_value or 0
                        elif stat_type == "Fouls":
                            live_stats[team_key]["fouls"] = stat_value or 0
                        elif stat_type == "Passes %":
                            live_stats[team_key]["pass_accuracy"] = stat_value or 0
                
                return live_stats
            
            return {}
            
        except Exception as e:
            print(f"⚠️ Error fetching live match statistics: {e}")
            return {}
    
    async def get_team_fixtures(self, team_id: int, season: int, status: str = None) -> List['Fixture']:
        """Get team fixtures for a specific season and status."""
        try:
            params = {
                "team": team_id,
                "season": season,
                "timezone": "Europe/Rome"
            }
            
            if status:
                params["status"] = status
            
            data = await self._make_request("/fixtures", params)
            
            if not data.get("response"):
                return []
            
            fixtures = []
            for fixture_data in data["response"]:
                fixture_info = fixture_data.get("fixture", {})
                teams_info = fixture_data.get("teams", {})
                venue_info = fixture_data.get("venue", {})
                
                # Create Team objects
                home_team = Team(
                    id=teams_info.get("home", {}).get("id", 0),
                    name=teams_info.get("home", {}).get("name", "Unknown"),
                    logo=teams_info.get("home", {}).get("logo", "")
                )
                
                away_team = Team(
                    id=teams_info.get("away", {}).get("id", 0),
                    name=teams_info.get("away", {}).get("name", "Unknown"),
                    logo=teams_info.get("away", {}).get("logo", "")
                )
                
                # Parse date
                from datetime import datetime
                import pytz
                date_str = fixture_info.get("date", "")
                if date_str:
                    try:
                        # Parse the ISO date string and convert to timezone-aware
                        if date_str.endswith("Z"):
                            date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                        else:
                            date = datetime.fromisoformat(date_str)
                        
                        # Ensure it's timezone-aware
                        if date.tzinfo is None:
                            date = pytz.UTC.localize(date)
                            
                        # Convert to local timezone for comparison
                        local_tz = pytz.timezone('Europe/Rome')
                        date = date.astimezone(local_tz)
                    except:
                        date = datetime.now(pytz.timezone('Europe/Rome'))
                else:
                    date = datetime.now(pytz.timezone('Europe/Rome'))
                
                # Create Fixture object
                from core.models import Fixture
                fixture = Fixture(
                    id=fixture_info.get("id", 0),
                    date=date,
                    status=fixture_info.get("status", {}).get("short", "NS"),
                    home_team=home_team,
                    away_team=away_team,
                    venue=venue_info.get("name", "")
                )
                
                fixtures.append(fixture)
            
            return fixtures
            
        except Exception as e:
            print(f"⚠️ Error fetching team fixtures: {e}")
            return []

    async def get_teams(self, country: str, league_name: str, season: int, league_id: int = None) -> List[Team]:
        """Get all teams for a specific league and season."""
        try:
            # Use provided league_id or get it from country/league_name
            if league_id is None:
                league_id = await self.get_league_id(country, league_name, season)
            if not league_id:
                return []
            
            # Check cache first
            cache_key = f"teams:{league_id}:{season}"
            cached_teams = await self.redis_cache.get_data(cache_key)
            
            if cached_teams:
                print(f"📋 Using cached teams for {league_name}")
                teams = []
                for team_data in cached_teams:
                    team = Team(
                        id=team_data["id"],
                        name=team_data["name"],
                        logo=team_data.get("logo")
                    )
                    teams.append(team)
                return teams
            
            print(f"🔄 Fetching teams for {league_name} from API...")
            
            params = {
                "league": league_id,
                "season": season
            }
            
            data = await self._make_request("/teams", params)
            
            if data.get("response"):
                teams = []
                team_data_list = []
                
                for team_info in data["response"]:
                    team = Team(
                        id=team_info["team"]["id"],
                        name=team_info["team"]["name"],
                        logo=team_info["team"]["logo"]
                    )
                    teams.append(team)
                    
                    # Prepare data for cache
                    team_data_list.append({
                        "id": team_info["team"]["id"],
                        "name": team_info["team"]["name"],
                        "logo": team_info["team"]["logo"]
                    })
                
                # Special handling for European competitions 2025/26 - filter to main tournament teams only
                if league_name in ["Champions League", "Europa League"] and season == 2025:
                    # Filter teams to only include those in the main tournament
                    teams = self._filter_european_competition_teams(teams, league_name)
                    print(f"🏆 Filtered {league_name} teams to main tournament: {len(teams)} teams")
                    
                    # Update team_data_list to match filtered teams
                    filtered_team_names = {team.name for team in teams}
                    team_data_list = [team_data for team_data in team_data_list 
                                    if team_data["name"] in filtered_team_names]
                
                # Cache the teams data
                await self.redis_cache.set_data(cache_key, team_data_list, "team_metadata")
                
                print(f"✅ Fetched {len(teams)} teams for {league_name}")
                return teams
            
            return []
            
        except Exception as e:
            print(f"❌ Error fetching teams: {e}")
            return []
    
    def _filter_european_competition_teams(self, teams: List[Team], league_name: str) -> List[Team]:
        """Filter European competition teams to only include main tournament teams."""
        if league_name == "Champions League":
            # Champions League 2025/26: 36 teams in main tournament
            return self._filter_champions_league_teams(teams)
        elif league_name == "Europa League":
            # Europa League 2025/26: 36 teams in main tournament
            return self._filter_europa_league_teams(teams)
        else:
            return teams
    
    def _filter_champions_league_teams(self, teams: List[Team]) -> List[Team]:
        """Filter Champions League teams to only include main tournament teams (36 teams)."""
        # Known main tournament teams for Champions League 2025/26
        # This list should be updated based on actual qualifiers
        main_tournament_teams = [
            # Top teams from major associations
            "Arsenal", "Chelsea", "Liverpool", "Manchester City", "Manchester United", "Newcastle",
            "Real Madrid", "Barcelona", "Atletico Madrid", "Real Sociedad", "Athletic Bilbao", "Girona",
            "Inter", "Milan", "Juventus", "Atalanta", "Roma", "Napoli",
            "Bayern München", "Borussia Dortmund", "Bayer Leverkusen", "RB Leipzig", "Stuttgart", "Eintracht Frankfurt",
            "Paris Saint Germain", "Monaco", "Lille", "Lyon", "Marseille", "Brest",
            "PSV", "Ajax", "Feyenoord",
            "Benfica", "Porto", "Sporting CP",
            "Club Brugge", "Anderlecht"
        ]
        
        # Filter teams to only include those in the main tournament
        filtered_teams = []
        for team in teams:
            if team.name in main_tournament_teams:
                filtered_teams.append(team)
        
        # If we don't have enough teams, return top teams by ID (usually better teams have lower IDs)
        if len(filtered_teams) < 36:
            # Sort by ID and take first 36
            sorted_teams = sorted(teams, key=lambda x: x.id)
            filtered_teams = sorted_teams[:36]
        
        return filtered_teams
    
    def _filter_europa_league_teams(self, teams: List[Team]) -> List[Team]:
        """Filter Europa League teams to only include main tournament teams (36 teams)."""
        # Known main tournament teams for Europa League 2025/26
        # These are typically teams that didn't qualify for Champions League but are strong
        main_tournament_teams = [
            # Teams from major leagues that didn't qualify for Champions League
            "Tottenham", "Aston Villa", "Brighton", "West Ham", "Wolves",
            "Villarreal", "Real Betis", "Sevilla", "Valencia", "Osasuna",
            "Lazio", "Fiorentina", "Torino", "Bologna", "Genoa",
            "Union Berlin", "Borussia Mönchengladbach", "Wolfsburg", "Augsburg", "Hoffenheim",
            "Nice", "Lens", "Rennes", "Toulouse", "Nantes",
            "AZ Alkmaar", "FC Utrecht", "Twente", "Heerenveen",
            "Braga", "Vitoria Guimaraes", "Arouca", "Gil Vicente",
            "Gent", "Antwerp", "Standard Liege", "Genk",
            # Plus teams from other associations
            "Shakhtar Donetsk", "Dynamo Kyiv", "Red Bull Salzburg", "Rapid Vienna",
            "Olympiacos", "Panathinaikos", "AEK Athens",
            "Fenerbahce", "Galatasaray", "Besiktas",
            "Celtic", "Rangers", "Hearts"
        ]
        
        # Filter teams to only include those in the main tournament
        filtered_teams = []
        for team in teams:
            if team.name in main_tournament_teams:
                filtered_teams.append(team)
        
        # If we don't have enough teams, return top teams by ID (usually better teams have lower IDs)
        if len(filtered_teams) < 36:
            # Sort by ID and take first 36
            sorted_teams = sorted(teams, key=lambda x: x.id)
            filtered_teams = sorted_teams[:36]
        
        return filtered_teams
    
    async def get_team_players(self, team_id: int, season: int) -> List[Dict[str, Any]]:
        """Get team players/roster for a specific season."""
        try:
            # Use the existing get_team_squad method
            players = await self.get_team_squad(team_id, season, auto_refresh=True)
            return players
            
        except Exception as e:
            print(f"❌ Error fetching team players: {e}")
            return []
    
    async def get_player_statistics(self, player_id: int, league_id: int, season: int) -> Dict[str, Any]:
        """Get player statistics for a specific season."""
        try:
            # Check cache first
            cache_key = f"player_stats:{player_id}:{league_id}:{season}"
            cached_stats = await self.redis_cache.get_data(cache_key)
            
            if cached_stats:
                print(f"📊 Using cached player stats for player {player_id}")
                return cached_stats
            
            print(f"🔄 Fetching player stats for player {player_id} from API...")
            
            params = {
                "player": player_id,
                "league": league_id,
                "season": season
            }
            
            data = await self._make_request("/players", params)
            
            if data.get("response") and len(data["response"]) > 0:
                player_data = data["response"][0]
                stats = player_data.get("statistics", [])
                
                if stats:
                    # Get statistics for the specific league
                    league_stats = None
                    for stat in stats:
                        if stat.get("league", {}).get("id") == league_id:
                            league_stats = stat
                            break
                    
                    if league_stats:
                        player_stats = {
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
                            "penalty": league_stats["penalty"]
                        }
                        
                        # Cache the player statistics
                        await self.redis_cache.set_data(cache_key, player_stats, "historical_data")
                        
                        print(f"✅ Fetched player stats for {player_data['player']['name']}")
                        return player_stats
            
            print(f"⚠️ No statistics found for player {player_id} in league {league_id}")
            return {}
            
        except Exception as e:
            print(f"❌ Error fetching player statistics: {e}")
            return {}
    
    async def force_update_team_statistics(self, team_id: int, league_id: int, season: int) -> Optional[TeamStats]:
        """Force update team statistics by bypassing cache."""
        try:
            print(f"🔄 Force updating team statistics for team {team_id}...")
            
            # Clear cache for this team
            cache_key = f"team_stats:{team_id}:{league_id}:{season}"
            self.redis_cache.delete_data(cache_key)
            
            # Fetch fresh data
            team_stats = await self.get_team_statistics(team_id, league_id, season)
            
            if team_stats:
                print(f"✅ Force updated team statistics for team {team_id}")
                return team_stats
            else:
                print(f"❌ Failed to update team statistics for team {team_id}")
                return None
                
        except Exception as e:
            print(f"❌ Error force updating team statistics: {e}")
            return None
    
    async def get_team_roster_fast(self, team_id: int, season: int) -> List[Dict]:
        """
        Ottieni roster team VELOCE (no filtering, no monitoring).
        Per utility menu - solo fetch e cache.
        Performance: < 2 secondi per API call
        """
        try:
            # Secondo documentazione: /players/squads?team={id}
            # Non serve season per squads
            params = {"team": team_id}
            
            data = await self._make_request("/players/squads", params)
            
            if data.get("response") and len(data["response"]) > 0:
                players = data["response"][0].get("players", [])
                return players
            
            return []
            
        except Exception as e:
            print(f"⚠️ Error fetching roster fast: {e}")
            return []
    
    async def force_update_team_roster(self, team_id: int, season: int) -> bool:
        """Force update team roster by bypassing cache."""
        try:
            print(f"🔄 Force updating roster for team {team_id}...")
            
            # Clear cache for this team
            cache_key = f"team_squad:{team_id}:{season}"
            self.redis_cache.delete_data(cache_key)
            
            # Fetch fresh data
            players = await self.get_team_players(team_id, season)
            
            if players:
                # Save the timestamp of this roster update
                from datetime import datetime
                now = datetime.now()
                update_key = f"roster_last_update:{team_id}:{season}"
                await self.redis_cache.set_data(update_key, now.isoformat(), "roster")
                
                print(f"✅ Force updated roster for team {team_id} ({len(players)} players)")
                return True
            else:
                print(f"❌ Failed to update roster for team {team_id}")
                return False
                
        except Exception as e:
            print(f"❌ Error force updating team roster: {e}")
            return False
    
    async def force_update_player_statistics(self, player_id: int, league_id: int, season: int) -> bool:
        """Force update player statistics by bypassing cache."""
        try:
            print(f"🔄 Force updating player statistics for player {player_id}...")
            
            # Clear cache for this player
            cache_key = f"player_stats:{player_id}:{league_id}:{season}"
            self.redis_cache.delete_data(cache_key)
            
            # Fetch fresh data
            player_stats = await self.get_player_statistics(player_id, league_id, season)
            
            if player_stats:
                print(f"✅ Force updated player statistics for player {player_id}")
                return True
            else:
                print(f"❌ Failed to update player statistics for player {player_id}")
                return False
                
        except Exception as e:
            print(f"❌ Error force updating player statistics: {e}")
            return False
