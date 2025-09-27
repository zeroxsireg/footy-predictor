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
            ("France", "Ligue 1"): 61
        }
        
        # Database cache for team shots/corners statistics
        from utils.database import ShotsCornerCache
        self.shots_corners_db = ShotsCornerCache()
    
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
    
    async def get_next_round_fixtures(self, league_id: int = None, season: int = None, country: str = None) -> List[Fixture]:
        """Get fixtures for the next round of matches."""
        if league_id is None:
            league_id = await self.get_league_id()
        
        season = season or self.settings.default_season
        
        # Get next fixtures (upcoming matches)
        params = {
            "league": league_id,
            "season": season,
            "next": "5"  # Get next 5 matches to avoid too many API calls
        }
        
        data = await self._make_request("/fixtures", params)
        
        # If no upcoming matches, try to get recent matches
        if not data.get("response"):
            params = {
                "league": league_id,
                "season": season,
                "last": "5"  # Get last 5 matches
            }
            data = await self._make_request("/fixtures", params)
        
        if not data.get("response"):
            raise FootballAPIError(f"No fixtures found for league {league_id} season {season}")
        
        fixtures = []
        country = country or self.settings.default_country
        for fixture_data in data["response"]:
            fixture = self._parse_fixture(fixture_data, country)
            fixtures.append(fixture)
        
        return fixtures
    
    async def get_team_statistics(self, team_id: int, league_id: int = None, season: int = None) -> TeamStats:
        """Get team statistics for a season."""
        if league_id is None:
            league_id = await self.get_league_id()
        
        season = season or self.settings.default_season
        
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
        
        # Get shots and corners from recent matches
        shots_corners_data = await self._get_team_shots_corners(team_id, league_id, season)
        team_stats.shots_total = shots_corners_data["shots_total"]
        team_stats.shots_on_target = shots_corners_data["shots_on_target"] 
        team_stats.corners = shots_corners_data["corners"]
        
        return team_stats
    
    async def _get_team_shots_corners(self, team_id: int, league_id: int, season: int) -> Dict[str, int]:
        """Get shots and corners statistics with database caching."""
        # Check database cache first
        cached_stats = self.shots_corners_db.get_team_stats(team_id, league_id, season)
        if cached_stats and cached_stats["matches_processed"] > 0:
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
                self.shots_corners_db.save_team_stats(team_id, league_id, season, 0, 0, 0, 0)
                return result
            
            total_shots = 0
            total_shots_on_target = 0
            total_corners = 0
            matches_processed = 0
            
            for fixture in data["response"]:
                match_id = fixture["fixture"]["id"]
                
                # Only process finished matches
                if fixture["fixture"]["status"]["short"] != "FT":
                    continue
                
                # Skip if already processed
                if self.shots_corners_db.is_match_processed(match_id):
                    continue
                
                matches_processed += 1
                
                # Get detailed match statistics
                match_data = await self._get_match_statistics(match_id, team_id)
                if match_data:
                    total_shots += match_data["shots"]
                    total_shots_on_target += match_data["shots_on_target"]
                    total_corners += match_data["corners"]
                    
                    # Mark match as processed
                    self.shots_corners_db.mark_match_processed(match_id, team_id, league_id, season)
            
            # Get existing cached data and add new data
            existing_stats = self.shots_corners_db.get_team_stats(team_id, league_id, season)
            if existing_stats:
                total_shots += existing_stats["shots_total"]
                total_shots_on_target += existing_stats["shots_on_target"]
                total_corners += existing_stats["corners"]
                matches_processed += existing_stats["matches_processed"]
            
            # Save to database
            self.shots_corners_db.save_team_stats(
                team_id, league_id, season,
                total_shots, total_shots_on_target, total_corners,
                matches_processed
            )
            
            result = {
                "shots_total": total_shots,
                "shots_on_target": total_shots_on_target,
                "corners": total_corners
            }
            
            print(f"✅ Processed {matches_processed} new matches for team {team_id}")
            return result
            
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
    
    async def get_team_squad(self, team_id: int, season: int) -> List[Dict[str, Any]]:
        """Get current squad (players) for a team in a specific season."""
        try:
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
                        "fouls_drawn": current_stats.get("fouls", {}).get("drawn", 0)
                    }
                    
                    players.append(player)
                
                return players
            
            return []
            
        except Exception as e:
            print(f"⚠️ Error fetching squad for team {team_id}: {e}")
            return []
    
    async def get_live_fixtures(self, leagues: List[int] = None) -> List[Dict[str, Any]]:
        """Get live fixtures from specified leagues or all leagues."""
        try:
            params = {"live": "all"}
            
            print(f"🔍 DEBUG: Calling /fixtures with params: {params}")
            data = await self._make_request("/fixtures", params)
            print(f"🔍 DEBUG: API response keys: {list(data.keys()) if data else 'No data'}")
            print(f"🔍 DEBUG: Total fixtures returned: {len(data.get('response', [])) if data else 0}")
            
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
                    
                    # Debug: print fixture details
                    home_team = teams_info.get("home", {}).get("name", "Unknown")
                    away_team = teams_info.get("away", {}).get("name", "Unknown")
                    league_name = league_info.get("name", "Unknown")
                    status = fixture_info.get("status", {}).get("short", "Unknown")
                    date = fixture_info.get("date", "Unknown")
                    
                    print(f"🔍 DEBUG: Found fixture: {home_team} vs {away_team} ({league_name}) - Status: {status} - Date: {date}")
                    
                    # Filter by date - only today's matches
                    if fixture_date != today:
                        print(f"🔍 DEBUG: Skipping fixture - not today's match (fixture date: {fixture_date}, today: {today})")
                        continue
                    
                    # Filter by leagues if specified
                    if leagues and league_info.get("id") not in leagues:
                        print(f"🔍 DEBUG: Skipping fixture - league {league_info.get('id')} not in target leagues")
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
