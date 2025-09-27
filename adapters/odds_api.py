"""Odds API adapter for fetching betting odds and bookmaker data."""

import httpx
from typing import List, Dict, Any, Optional
import asyncio
import time
from dataclasses import dataclass

from core.config import get_settings


class OddsAPIError(Exception):
    """Exception raised for Odds API errors."""
    pass


@dataclass
class BookmakerOdds:
    """Odds from a specific bookmaker."""
    bookmaker_id: int
    bookmaker_name: str
    bet_id: int
    bet_name: str
    values: List[Dict[str, Any]]  # [{"value": "Home", "odd": "2.10"}, ...]


@dataclass
class FixtureOdds:
    """All odds for a specific fixture."""
    fixture_id: int
    bookmakers: List[BookmakerOdds]


class OddsAPIClient:
    """Client for the Football Odds API."""
    
    def __init__(self):
        self.settings = get_settings()
        self.base_url = self.settings.api_football_base
        self.headers = {
            "x-apisports-key": self.settings.api_football_key
        }
        self.last_request_time = 0
        self.min_request_interval = 1.0  # Minimum 1 second between requests
        
        # Cache for bookmakers and bets
        self._bookmakers_cache = None
        self._bets_cache = None
        
        # Common bet IDs (will be populated dynamically)
        self.bet_ids = {
            "match_winner": None,  # 1X2
            "over_under_25": None,  # Over/Under 2.5 Goals
            "both_teams_score": None,  # BTTS
            "exact_score": None,  # Correct Score
            "over_under_15": None,  # Over/Under 1.5 Goals
            "over_under_35": None,  # Over/Under 3.5 Goals
        }
    
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
                        raise OddsAPIError(f"Rate limit exceeded: {data['errors']['rateLimit']}")
                    else:
                        raise OddsAPIError(f"API errors: {data['errors']}")
                
                return data
            except httpx.HTTPError as e:
                raise OddsAPIError(f"Odds API request failed: {e}")
    
    async def get_available_bets(self, search: str = None) -> List[Dict[str, Any]]:
        """Get all available bet types."""
        if self._bets_cache:
            return self._bets_cache
        
        params = {}
        if search:
            params["search"] = search
        
        try:
            data = await self._make_request("/odds/bets", params)
            
            if data.get("response"):
                response_data = data["response"]
                self._bets_cache = response_data
                # Populate bet_ids mapping
                self._populate_bet_ids(response_data)
                return response_data
            
            return []
        except Exception as e:
            print(f"⚠️ Warning: Could not fetch available bets: {e}")
            return []
    
    async def get_bookmakers(self, search: str = None) -> List[Dict[str, Any]]:
        """Get all available bookmakers."""
        if self._bookmakers_cache:
            return self._bookmakers_cache
        
        params = {}
        if search:
            params["search"] = search
        
        try:
            data = await self._make_request("/odds/bookmakers", params)
            
            if data.get("response"):
                self._bookmakers_cache = data["response"]
                return data["response"]
            
            return []
        except Exception as e:
            print(f"⚠️ Warning: Could not fetch bookmakers: {e}")
            return []
    
    async def get_fixture_odds(self, fixture_id: int, bet_ids: List[int] = None, 
                              bookmaker_ids: List[int] = None) -> Optional[FixtureOdds]:
        """Get odds for a specific fixture."""
        params = {"fixture": fixture_id}
        
        # Add bet filters if specified
        if bet_ids:
            for bet_id in bet_ids:
                params["bet"] = bet_id
                break  # API only supports one bet at a time
        
        # Add bookmaker filters if specified
        if bookmaker_ids:
            for bookmaker_id in bookmaker_ids:
                params["bookmaker"] = bookmaker_id
                break  # API only supports one bookmaker at a time
        
        try:
            data = await self._make_request("/odds", params)
            
            if not data.get("response"):
                return None
            
            return self._parse_fixture_odds(fixture_id, data["response"])
            
        except Exception as e:
            print(f"⚠️ Warning: Could not fetch odds for fixture {fixture_id}: {e}")
            return None
    
    async def get_popular_odds_for_fixture(self, fixture_id: int, preferred_bookmakers: List[int] = None) -> Dict[str, Any]:
        """Get the most popular odds for key markets."""
        # Ensure we have bet IDs
        if not self._bets_cache:
            await self.get_available_bets()
        
        popular_odds = {
            "match_winner": None,
            "over_under_25": None,
            "both_teams_score": None,
            "exact_score": None
        }
        
        # Get odds for key markets
        for market, bet_id in self.bet_ids.items():
            if bet_id and market in popular_odds:
                try:
                    # Try preferred bookmakers first, then fallback to any bookmaker
                    fixture_odds = None
                    
                    if preferred_bookmakers:
                        for bookmaker_id in preferred_bookmakers:
                            fixture_odds = await self.get_fixture_odds(fixture_id, [bet_id], [bookmaker_id])
                            if fixture_odds and fixture_odds.bookmakers:
                                break
                    
                    # Fallback to any bookmaker if preferred ones don't have odds
                    if not fixture_odds or not fixture_odds.bookmakers:
                        fixture_odds = await self.get_fixture_odds(fixture_id, [bet_id])
                    
                    if fixture_odds and fixture_odds.bookmakers:
                        # Prefer bookmakers in the preferred list
                        selected_bookmaker = fixture_odds.bookmakers[0]
                        if preferred_bookmakers:
                            for bookmaker in fixture_odds.bookmakers:
                                if bookmaker.bookmaker_id in preferred_bookmakers:
                                    selected_bookmaker = bookmaker
                                    break
                        
                        popular_odds[market] = selected_bookmaker
                        
                except Exception as e:
                    print(f"⚠️ Could not get {market} odds: {e}")
                    continue
        
        return popular_odds
    
    def _populate_bet_ids(self, bets: List[Dict[str, Any]]):
        """Populate bet_ids mapping from available bets."""
        bet_name_mapping = {
            "match_winner": ["Match Winner", "1X2", "Home/Draw/Away"],
            "over_under_25": ["Goals Over/Under", "Over/Under 2.5", "Total Goals"],
            "both_teams_score": ["Both Teams Score", "BTTS", "Both Teams To Score"],
            "exact_score": ["Correct Score", "Exact Score", "Final Result"],
            "over_under_15": ["Over/Under 1.5", "Goals Over/Under 1.5"],
            "over_under_35": ["Over/Under 3.5", "Goals Over/Under 3.5"]
        }
        
        for bet in bets:
            if not bet or not isinstance(bet, dict):
                continue
            
            bet_name = str(bet.get("name", "")).lower() if bet.get("name") else ""
            bet_id = bet.get("id")
            
            if not bet_name or bet_id is None:
                continue
            
            for market, possible_names in bet_name_mapping.items():
                for possible_name in possible_names:
                    if possible_name.lower() in bet_name:
                        self.bet_ids[market] = bet_id
                        break
    
    def _parse_fixture_odds(self, fixture_id: int, odds_data: List[Dict[str, Any]]) -> FixtureOdds:
        """Parse odds data for a fixture."""
        bookmakers = []
        
        for fixture_odds in odds_data:
            if fixture_odds.get("fixture", {}).get("id") != fixture_id:
                continue
            
            for bookmaker_data in fixture_odds.get("bookmakers", []):
                bookmaker_id = bookmaker_data.get("id")
                bookmaker_name = bookmaker_data.get("name", "Unknown")
                
                for bet_data in bookmaker_data.get("bets", []):
                    bet_id = bet_data.get("id")
                    bet_name = bet_data.get("name", "Unknown")
                    values = bet_data.get("values", [])
                    
                    bookmakers.append(BookmakerOdds(
                        bookmaker_id=bookmaker_id,
                        bookmaker_name=bookmaker_name,
                        bet_id=bet_id,
                        bet_name=bet_name,
                        values=values
                    ))
        
        return FixtureOdds(
            fixture_id=fixture_id,
            bookmakers=bookmakers
        )
    
    def find_best_odds(self, fixture_odds: FixtureOdds, bet_name: str, selection: str) -> Optional[Dict[str, Any]]:
        """Find the best odds for a specific bet and selection."""
        best_odds = None
        best_value = 0.0
        
        for bookmaker in fixture_odds.bookmakers:
            if bet_name.lower() in bookmaker.bet_name.lower():
                for value in bookmaker.values:
                    if selection.lower() in value.get("value", "").lower():
                        odd_value = float(value.get("odd", 0))
                        if odd_value > best_value:
                            best_value = odd_value
                            best_odds = {
                                "bookmaker": bookmaker.bookmaker_name,
                                "selection": value.get("value"),
                                "odds": odd_value,
                                "bet": bookmaker.bet_name
                            }
        
        return best_odds
