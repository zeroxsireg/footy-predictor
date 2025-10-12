"""Bookmaker Manager for fetching and managing betting odds."""

import asyncio
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from adapters.odds_api import OddsAPIClient, FixtureOdds
from models.daily_pick import DailyPick
from core.config import get_settings


@dataclass
class OddsMapping:
    """Mapping between our market and API bet structure."""
    our_market: str  # e.g., "Match Goals"
    our_selection: str  # e.g., "Over 2.5"
    bet_id: Optional[int]  # API bet ID
    api_selection: str  # e.g., "Over 2.5"


class BookmakerManager:
    """Manager for fetching and processing bookmaker odds."""
    
    def __init__(self):
        self.settings = get_settings()
        self.odds_client = OddsAPIClient()
        
        # Cache per fixture per evitare richieste multiple
        self._fixture_odds_cache: Dict[int, Dict[str, any]] = {}
        
        # Mapping tra i nostri mercati e i bet IDs delle API
        self.market_mappings = {
            # Goals markets
            "Match Goals": {
                "Over 0.5": (1, "Over 0.5"),
                "Over 1.5": (1, "Over 1.5"),
                "Over 2.5": (1, "Over 2.5"),
                "Over 3.5": (1, "Over 3.5"),
                "Over 4.5": (1, "Over 4.5"),
                "Under 2.5": (1, "Under 2.5"),
                "Under 3.5": (1, "Under 3.5"),
            },
            # BTTS
            "Both Teams to Score": {
                "Yes": (8, "Yes"),
                "No": (8, "No"),
            },
            # Match Result
            "Match Result": {
                "1 (Home Win)": (1, "Home"),
                "X (Draw)": (1, "Draw"),
                "2 (Away Win)": (1, "Away"),
                "Home Win": (1, "Home"),
                "Draw": (1, "Draw"),
                "Away Win": (1, "Away"),
            },
            # Corners (se disponibili)
            "Total Corners": {
                "Over 8.5": (12, "Over 8.5"),
                "Over 9.5": (12, "Over 9.5"),
                "Over 10.5": (12, "Over 10.5"),
                "Over 11.5": (12, "Over 11.5"),
                "Over 12.5": (12, "Over 12.5"),
                "Under 9.5": (12, "Under 9.5"),
                "Under 10.5": (12, "Under 10.5"),
            },
            # Cards (se disponibili)
            "Total Cards": {
                "Over 2.5": (11, "Over 2.5"),
                "Over 3.5": (11, "Over 3.5"),
                "Over 4.5": (11, "Over 4.5"),
                "Under 3.5": (11, "Under 3.5"),
                "Under 4.5": (11, "Under 4.5"),
            },
        }
    
    async def initialize(self):
        """Initialize the bookmaker manager by fetching available bets."""
        print("🎲 Inizializzazione Bookmaker Manager...")
        try:
            # Fetch available bets to populate bet_ids
            bets = await self.odds_client.get_available_bets()
            print(f"✅ Trovati {len(bets)} tipi di scommessa disponibili")
            
            # Fetch available bookmakers
            bookmakers = await self.odds_client.get_bookmakers()
            print(f"✅ Trovati {len(bookmakers)} bookmaker disponibili")
            
            return True
        except Exception as e:
            print(f"⚠️ Errore inizializzazione: {e}")
            return False
    
    async def get_odds_for_pick(self, pick: DailyPick, fixture_id: int) -> Optional[Tuple[str, float]]:
        """
        Get real odds for a specific pick.
        
        Returns:
            Tuple of (bookmaker_name, odds_value) or None if not found
        """
        # Check cache first
        cache_key = f"{fixture_id}_{pick.market}_{pick.selection}"
        if cache_key in self._fixture_odds_cache:
            return self._fixture_odds_cache[cache_key]
        
        # Get bet_id and api_selection from our mappings
        bet_info = self._get_bet_mapping(pick.market, pick.selection)
        if not bet_info:
            return None
        
        bet_id, api_selection = bet_info
        
        try:
            # Fetch odds from preferred bookmaker (Bet365)
            fixture_odds = await self.odds_client.get_fixture_odds(
                fixture_id=fixture_id,
                bet_ids=[bet_id],
                bookmaker_ids=self.settings.preferred_bookmakers
            )
            
            if not fixture_odds or not fixture_odds.bookmakers:
                return None
            
            # Find matching selection
            for bookmaker_odds in fixture_odds.bookmakers:
                for value in bookmaker_odds.values:
                    if self._match_selection(value.get("value", ""), api_selection):
                        odds_value = float(value.get("odd", 0))
                        result = (bookmaker_odds.bookmaker_name, odds_value)
                        
                        # Cache the result
                        self._fixture_odds_cache[cache_key] = result
                        return result
            
            return None
            
        except Exception as e:
            print(f"⚠️ Errore recupero quote per {pick.market} - {pick.selection}: {e}")
            return None
    
    async def enrich_picks_with_odds(self, picks: List[DailyPick], 
                                    fixture_ids: Dict[str, int]) -> List[DailyPick]:
        """
        Enrich a list of picks with real odds from bookmakers.
        
        Args:
            picks: List of DailyPick objects
            fixture_ids: Mapping of "Home vs Away" to fixture_id
        
        Returns:
            List of enriched DailyPick objects
        """
        print(f"\n💰 Recupero quote reali per {len(picks)} picks...")
        
        enriched_picks = []
        success_count = 0
        
        for pick in picks:
            # Get fixture_id for this pick
            match_key = f"{pick.home_team} vs {pick.away_team}"
            fixture_id = fixture_ids.get(match_key)
            
            if not fixture_id:
                enriched_picks.append(pick)
                continue
            
            # Get real odds
            odds_info = await self.get_odds_for_pick(pick, fixture_id)
            
            if odds_info:
                bookmaker, odds_value = odds_info
                pick.bookmaker = bookmaker
                pick.real_odds = odds_value
                success_count += 1
            
            enriched_picks.append(pick)
            
            # Rate limiting
            await asyncio.sleep(0.5)
        
        print(f"✅ Quote trovate per {success_count}/{len(picks)} picks")
        return enriched_picks
    
    def _get_bet_mapping(self, market: str, selection: str) -> Optional[Tuple[int, str]]:
        """
        Get bet_id and API selection for our market/selection.
        
        Returns:
            Tuple of (bet_id, api_selection) or None
        """
        # Normalize market name (remove team names for team-specific markets)
        base_market = self._normalize_market(market)
        
        # Check if we have a mapping for this market
        if base_market in self.market_mappings:
            market_map = self.market_mappings[base_market]
            
            # Normalize selection
            normalized_selection = self._normalize_selection(selection)
            
            # Try exact match first
            if normalized_selection in market_map:
                return market_map[normalized_selection]
            
            # Try partial match
            for key, value in market_map.items():
                if key.lower() in normalized_selection.lower() or \
                   normalized_selection.lower() in key.lower():
                    return value
        
        return None
    
    def _normalize_market(self, market: str) -> str:
        """Normalize market name by removing team-specific parts."""
        # Remove team names (anything before "Shots", "Corners", "Cards")
        for keyword in ["Shots", "Corners", "Cards", "Goals"]:
            if keyword in market:
                # For team-specific markets, we still want the base type
                if "Total" in market or "Match" in market:
                    return market
                # For now, we don't have team-specific odds mappings
                return f"Team {keyword}"
        
        return market
    
    def _normalize_selection(self, selection: str) -> str:
        """Normalize selection string."""
        # Remove extra spaces and convert to title case
        return " ".join(selection.split())
    
    def _match_selection(self, api_value: str, our_selection: str) -> bool:
        """Check if API value matches our selection."""
        api_lower = api_value.lower().strip()
        our_lower = our_selection.lower().strip()
        
        # Direct match
        if api_lower == our_lower:
            return True
        
        # Match variations
        if "over" in our_lower and "over" in api_lower:
            # Extract numbers
            our_num = self._extract_number(our_lower)
            api_num = self._extract_number(api_lower)
            return our_num == api_num
        
        if "under" in our_lower and "under" in api_lower:
            our_num = self._extract_number(our_lower)
            api_num = self._extract_number(api_lower)
            return our_num == api_num
        
        # Match result variations
        if "home" in our_lower and "home" in api_lower:
            return True
        if "away" in our_lower and "away" in api_lower:
            return True
        if "draw" in our_lower and "draw" in api_lower:
            return True
        
        # BTTS variations
        if our_lower in ["yes", "no"] and api_lower in ["yes", "no"]:
            return our_lower == api_lower
        
        return False
    
    def _extract_number(self, text: str) -> Optional[float]:
        """Extract numeric value from text."""
        import re
        match = re.search(r'\d+\.?\d*', text)
        if match:
            return float(match.group())
        return None
    
    def get_odds_summary(self) -> Dict[str, any]:
        """Get summary of odds fetched."""
        return {
            "total_cached": len(self._fixture_odds_cache),
            "unique_fixtures": len(set(k.split("_")[0] for k in self._fixture_odds_cache.keys()))
        }


async def test_bookmaker_manager():
    """Test function for BookmakerManager."""
    manager = BookmakerManager()
    await manager.initialize()
    
    # Test with a sample pick
    from datetime import datetime
    
    test_pick = DailyPick(
        match_id=1234,
        home_team="AS Roma",
        away_team="Inter",
        market="Match Goals",
        selection="Over 2.5",
        confidence="HIGH",
        percentage=75.0,
        odds_range=None,
        reasoning="Test pick",
        match_time=datetime.now(),
        league="Serie A",
        real_odds=None,
        bookmaker=None
    )
    
    # Test odds fetching
    odds = await manager.get_odds_for_pick(test_pick, 1234)
    print(f"\n📊 Test Result: {odds}")
    
    # Test enrichment
    fixture_ids = {"AS Roma vs Inter": 1234}
    enriched = await manager.enrich_picks_with_odds([test_pick], fixture_ids)
    
    print(f"\n✅ Enriched Pick:")
    print(f"   Market: {enriched[0].market}")
    print(f"   Selection: {enriched[0].selection}")
    print(f"   Bookmaker: {enriched[0].bookmaker}")
    print(f"   Real Odds: {enriched[0].real_odds}")


if __name__ == "__main__":
    asyncio.run(test_bookmaker_manager())

