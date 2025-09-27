"""Interactive CLI menu for league and match selection."""

import asyncio
from typing import List, Tuple, Optional
from datetime import datetime

from core.config import get_settings
from adapters.football_api import FootballAPIClient, FootballAPIError
from core.models import Fixture
from core.analyzer import MatchAnalyzer
from cli.simple_main import display_matchday


class InteractiveMenu:
    """Interactive menu for selecting leagues and matches."""
    
    def __init__(self):
        self.settings = get_settings()
        self.api_client = FootballAPIClient()
        self.analyzer = MatchAnalyzer()
        
        # Top 5 European leagues + European competitions
        self.available_leagues = {
            "1": ("Italy", "Serie A", "🇮🇹"),
            "2": ("England", "Premier League", "🏴󠁧󠁢󠁥󠁮󠁧󠁿"),
            "3": ("Spain", "La Liga", "🇪🇸"),
            "4": ("Germany", "Bundesliga", "🇩🇪"),
            "5": ("France", "Ligue 1", "🇫🇷"),
            "6": ("Europe", "UEFA Champions League", "🏆"),
            "7": ("Europe", "UEFA Europa League", "🥈")
        }
    
    async def run(self):
        """Run the interactive menu."""
        try:
            print("\n🏆 FOOTY PREDICTOR - ANALISI INTERATTIVA")
            print("=" * 50)
            
            # Step 1: Select league
            league_info = self.select_league()
            if not league_info:
                return
            
            country, league_name, flag = league_info
            print(f"\n⏳ Recupero partite per {flag} {league_name}...")
            
            # Step 2: Get fixtures for selected league
            fixtures = await self.get_league_fixtures(country, league_name)
            if not fixtures:
                print("❌ Nessuna partita trovata per questo campionato.")
                return
            
            # Step 3: Select specific match
            selected_fixture = self.select_fixture(fixtures, league_name, flag)
            if not selected_fixture:
                return
            
            # Step 4: Analyze selected match
            print(f"\n⏳ Analisi in corso per {selected_fixture.home_team.name} vs {selected_fixture.away_team.name}...")
            await self.analyze_single_fixture(selected_fixture, country, league_name)
            
        except KeyboardInterrupt:
            print("\n\n👋 Arrivederci!")
        except Exception as e:
            print(f"\n❌ Errore: {e}")
    
    def select_league(self) -> Optional[Tuple[str, str, str]]:
        """Display league selection menu and return selected league info."""
        print("\n📋 SELEZIONA CAMPIONATO:")
        print("-" * 30)
        
        for key, (country, league, flag) in self.available_leagues.items():
            print(f"{key}. {flag} {league} ({country})")
        
        print("0. Esci")
        
        while True:
            try:
                choice = input("\n🎯 Scegli un campionato (1-7, 0 per uscire): ").strip()
                
                if choice == "0":
                    print("👋 Arrivederci!")
                    return None
                
                if choice in self.available_leagues:
                    return self.available_leagues[choice]
                else:
                    print("❌ Scelta non valida. Riprova.")
                    
            except (ValueError, KeyboardInterrupt):
                print("\n👋 Arrivederci!")
                return None
    
    async def get_league_fixtures(self, country: str, league_name: str) -> List[Fixture]:
        """Get fixtures for the selected league."""
        try:
            # Get league ID
            league_id = await self.api_client.get_league_id(country, league_name, self.settings.default_season)
            
            # Get fixtures with country for timezone conversion
            fixtures = await self.api_client.get_next_round_fixtures(league_id, self.settings.default_season, country)
            
            return fixtures
            
        except FootballAPIError as e:
            print(f"❌ Errore API: {e}")
            return []
    
    def select_fixture(self, fixtures: List[Fixture], league_name: str, flag: str) -> Optional[Fixture]:
        """Display fixture selection menu and return selected fixture."""
        print(f"\n⚽ PARTITE DISPONIBILI - {flag} {league_name}")
        print("=" * 50)
        
        # Group fixtures by date
        fixtures_by_date = {}
        for fixture in fixtures:
            date_key = fixture.date.strftime("%d/%m/%Y")
            if date_key not in fixtures_by_date:
                fixtures_by_date[date_key] = []
            fixtures_by_date[date_key].append(fixture)
        
        # Display fixtures grouped by date
        fixture_index = 1
        fixture_map = {}
        
        for date, date_fixtures in sorted(fixtures_by_date.items()):
            print(f"\n📅 {date}")
            print("-" * 20)
            
            for fixture in date_fixtures:
                time_str = fixture.date.strftime("%H:%M")
                status_emoji = "🔴" if fixture.status == "FT" else "🟢" if fixture.status in ["1H", "2H", "HT"] else "⚪"
                
                print(f"{fixture_index:2d}. {status_emoji} {fixture.home_team.name} vs {fixture.away_team.name}")
                print(f"     🕐 {time_str} | 🏟️ {fixture.venue or 'N/A'}")
                
                fixture_map[str(fixture_index)] = fixture
                fixture_index += 1
        
        print(f"\n0. Torna al menu campionati")
        
        while True:
            try:
                choice = input(f"\n🎯 Scegli una partita (1-{len(fixtures)}, 0 per tornare indietro): ").strip()
                
                if choice == "0":
                    return None
                
                if choice in fixture_map:
                    return fixture_map[choice]
                else:
                    print("❌ Scelta non valida. Riprova.")
                    
            except (ValueError, KeyboardInterrupt):
                print("\n👋 Arrivederci!")
                return None
    
    async def analyze_single_fixture(self, fixture: Fixture, country: str, league_name: str):
        """Analyze a single fixture with full statistics."""
        try:
            # Get league ID
            league_id = await self.api_client.get_league_id(country, league_name, self.settings.default_season)
            
            # Analyze the match
            prediction = await self.analyzer._analyze_single_match(fixture, league_id, self.settings.default_season)
            
            # Display results using existing display function
            await display_matchday([prediction], league_id, self.settings.default_season)
            
            # Ask if user wants to analyze another match
            print("\n" + "=" * 50)
            choice = input("🔄 Vuoi analizzare un'altra partita? (s/n): ").strip().lower()
            
            if choice in ['s', 'si', 'y', 'yes']:
                await self.run()
        
        except Exception as e:
            print(f"❌ Errore nell'analisi: {e}")
    
    async def run_prematch_menu(self):
        """Run pre-match analysis menu."""
        # Show available leagues
        print("\n📋 SELEZIONA CAMPIONATO:")
        print("-" * 30)
        for key, (country, league, flag) in self.available_leagues.items():
            print(f"{key}. {flag} {league} ({country})")
        print("0. Torna al menu principale")
        
        # Get user choice
        choice = input(f"\n🎯 Scegli un campionato (1-{len(self.available_leagues)}, 0 per tornare indietro): ").strip()
        
        if choice == "0":
            return
        
        if choice not in self.available_leagues:
            print("❌ Scelta non valida.")
            return
        
        country, league_name, flag = self.available_leagues[choice]
        
        print(f"\n⏳ Recupero partite per {flag} {league_name}...")
        
        # Get fixtures
        fixtures = await self.get_league_fixtures(country, league_name)
        
        if not fixtures:
            print("❌ Nessuna partita trovata per questo campionato.")
            return
        
        # Select fixture
        selected_fixture = self.select_fixture(fixtures, league_name, flag)
        
        if selected_fixture:
            await self.analyze_single_fixture(selected_fixture, country, league_name)
            
            # Ask if user wants to analyze another match
            print("\n" + "=" * 50)
            choice = input("🔄 Vuoi analizzare un'altra partita? (s/n): ").strip().lower()
            
            if choice in ['s', 'si', 'y', 'yes']:
                await self.run_prematch_menu()


async def run_interactive_menu():
    """Main entry point for interactive menu."""
    from cli.main_menu import run_main_menu
    await run_main_menu()
