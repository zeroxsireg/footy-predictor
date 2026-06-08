"""Interactive CLI menu for league and match selection."""

import asyncio
from typing import List, Tuple, Optional
from datetime import datetime

from core.config import get_settings
from adapters.football_api import FootballAPIClient, FootballAPIError
from core.models import Fixture
from core.analyzer import MatchAnalyzer
from cli.match_display import display_matchday
from config.leagues import get_league_manager


class InteractiveMenu:
    """Interactive menu for selecting leagues and matches."""
    
    def __init__(self):
        self.settings = get_settings()
        self.api_client = FootballAPIClient()
        self.analyzer = MatchAnalyzer()
        self.league_manager = get_league_manager()
        
        # Build available leagues from enabled leagues (excluding cups)
        self.available_leagues = {}
        idx = 1
        for league in self.league_manager.get_enabled_leagues():
            if not league.is_cup:
                self.available_leagues[str(idx)] = (
                    league.country, 
                    league.name, 
                    league.flag, 
                    league.country  # country_it (for display)
                )
                idx += 1
        
        # Build available cups from enabled leagues (only cups)
        self.available_cups = {}
        for league in self.league_manager.get_enabled_leagues():
            if league.is_cup:
                self.available_cups[str(idx)] = (
                    league.country,
                    league.name,
                    league.flag,
                    league.country  # country_it (for display)
                )
                idx += 1
    
    async def run(self):
        """Run the interactive menu."""
        try:
            print("\n🏆 FOOTY PREDICTOR - ANALISI INTERATTIVA")
            print("=" * 50)
            
            # Step 1: Select league
            league_info = self.select_league()
            if not league_info:
                return
            
            country, league_name, flag, country_it = league_info
            print(f"\n⏳ Recupero partite per {flag} {country_it} {league_name}...")
            
            # Step 2: Get fixtures for selected league
            fixtures = await self.get_league_fixtures(country, league_name)
            if not fixtures:
                print("❌ Nessuna partita trovata per questo campionato.")
                return
            
            # Step 3: Select specific match
            selected_fixture = self.select_fixture(fixtures, league_name, f"{flag} {country_it}")
            if not selected_fixture:
                return
            
            # Step 4: Analyze selected match
            print(f"\n⏳ Analisi in corso per {selected_fixture.home_team.name} vs {selected_fixture.away_team.name}...")
            await self.analyze_single_fixture(selected_fixture, country, league_name)
            
        except KeyboardInterrupt:
            print("\n\n👋 Arrivederci!")
        except Exception as e:
            print(f"\n❌ Errore: {e}")
    
    def select_league(self) -> Optional[Tuple[str, str, str, str]]:
        """Display league selection menu and return selected league info."""
        print("\n📋 SELEZIONA CAMPIONATO:")
        print("-" * 30)
        
        # Campionati nazionali
        print("🏆 CAMPIONATI NAZIONALI:")
        for key, (country, league, flag, country_it) in self.available_leagues.items():
            print(f"{key}. {flag} {country_it} - {league}")
        
        print("\n🏅 COPPE EUROPEE:")
        for key, (country, league, flag, country_it) in self.available_cups.items():
            print(f"{key}. {flag} {league}")
        
        print("\n0. Esci")
        
        while True:
            try:
                choice = input("\n🎯 Scegli un campionato (1-7, 0 per uscire): ").strip()
                
                if choice == "0":
                    print("👋 Arrivederci!")
                    return None
                
                # Check in leagues first, then cups
                if choice in self.available_leagues:
                    return self.available_leagues[choice]
                elif choice in self.available_cups:
                    return self.available_cups[choice]
                else:
                    print("❌ Scelta non valida. Riprova.")
                    
            except (ValueError, KeyboardInterrupt):
                print("\n👋 Arrivederci!")
                return None
    
    async def get_league_fixtures(self, country: str, league_name: str) -> tuple[List[Fixture], int]:
        """Get fixtures for the selected league."""
        try:
            # Get league ID
            league_id = await self.api_client.get_league_id(country, league_name, self.settings.default_season)
            
            # Get fixtures with country for timezone conversion
            fixtures, round_number = await self.api_client.get_next_round_fixtures(league_id, self.settings.default_season, country)
            
            return fixtures, round_number
            
        except FootballAPIError as e:
            print(f"❌ Errore API: {e}")
            return [], 1
    
    def select_fixture(self, fixtures: List[Fixture], league_name: str, flag: str, round_number: int = None) -> Optional[Fixture]:
        """Display fixture selection menu and return selected fixture."""
        round_text = f" - Giornata {round_number}" if round_number else ""
        print(f"\n⚽ PARTITE DISPONIBILI - {flag} {league_name}{round_text}")
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
            # Get the first fixture to extract the day of the week
            first_fixture = date_fixtures[0]
            day_name = first_fixture.date.strftime("%A")  # Full day name (e.g., "Monday")
            day_name_it = {
                "Monday": "Lunedì",
                "Tuesday": "Martedì", 
                "Wednesday": "Mercoledì",
                "Thursday": "Giovedì",
                "Friday": "Venerdì",
                "Saturday": "Sabato",
                "Sunday": "Domenica"
            }.get(day_name, day_name)
            
            print(f"\n📅 {date} ({day_name_it})")
            print("-" * 20)
            
            for fixture in date_fixtures:
                time_str = fixture.date.strftime("%H:%M")
                status_emoji = "🔴" if fixture.status == "FT" else "🟢" if fixture.status in ["1H", "2H", "HT"] else "⚽"
                
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
            import traceback
            traceback.print_exc()
    
    async def run_prematch_menu(self):
        """Run pre-match analysis menu."""
        # Show available leagues
        print("\n📋 SELEZIONA CAMPIONATO:")
        print("-" * 30)
        
        # Campionati nazionali
        print("🏆 CAMPIONATI NAZIONALI:")
        for key, (country, league, flag, country_it) in self.available_leagues.items():
            print(f"{key}. {flag} {country_it} - {league}")
        
        print("\n🏅 COPPE EUROPEE:")
        for key, (country, league, flag, country_it) in self.available_cups.items():
            print(f"{key}. {flag} {league}")
        
        print("\n0. Torna al menu principale")
        
        # Get user choice
        choice = input(f"\n🎯 Scegli un campionato (1-7, 0 per tornare indietro): ").strip()
        
        if choice == "0":
            return
        
        # Check in leagues first, then cups
        if choice in self.available_leagues:
            country, league_name, flag, country_it = self.available_leagues[choice]
        elif choice in self.available_cups:
            country, league_name, flag, country_it = self.available_cups[choice]
        else:
            print("❌ Scelta non valida.")
            return
        
        # No special cases for PRE-MATCH menu
        
        print(f"\n⏳ Recupero partite per {flag} {country_it} {league_name}...")
        
        # Get fixtures
        fixtures, round_number = await self.get_league_fixtures(country, league_name)
        
        if not fixtures:
            print("❌ Nessuna partita trovata per questo campionato.")
            return
        
        # Select fixture
        selected_fixture = self.select_fixture(fixtures, league_name, flag, round_number)
        
        if selected_fixture:
            await self.analyze_single_fixture(selected_fixture, country, league_name)
            
            # Ask if user wants to analyze another match
            print("\n" + "=" * 50)
            choice = input("🔄 Vuoi analizzare un'altra partita? (s/n): ").strip().lower()
            
            if choice in ['s', 'si', 'y', 'yes']:
                await self.run_prematch_menu()
    
    async def _run_all_cups_prematch(self):
        """Run pre-match analysis for all European cups."""
        print("\n🏆 ANALISI PRE-MATCH TUTTE LE COPPE EUROPEE")
        print("=" * 50)
        print("⚠️  Questa operazione mostrerà le prossime partite di tutte le coppe")
        
        # Define all European cups
        all_cups = [
            ("Europe", "UEFA Champions League", "🏆", "Europa"),
            ("Europe", "UEFA Europa League", "🥈", "Europa")
        ]
        
        all_fixtures = []
        
        for country, league_name, flag, country_it in all_cups:
            print(f"\n📊 Recuperando partite per {flag} {league_name}...")
            try:
                fixtures, round_number = await self.get_league_fixtures(country, league_name)
                if fixtures:
                    all_fixtures.extend([(fixture, league_name, flag, round_number) for fixture in fixtures])
                    print(f"✅ Trovate {len(fixtures)} partite per {league_name}")
                else:
                    print(f"⚠️ Nessuna partita trovata per {league_name}")
            except Exception as e:
                print(f"❌ Errore per {league_name}: {e}")
        
        # Display all fixtures
        if all_fixtures:
            print(f"\n🎉 TROVATE {len(all_fixtures)} PARTITE IN TUTTE LE COPPE!")
            print("=" * 50)
            
            # Show all fixtures with numbers
            for i, (fixture, league_name, flag, round_number) in enumerate(all_fixtures, 1):
                time_str = fixture.date.strftime("%d/%m %H:%M")
                print(f"{i:2d}. ⚽ {fixture.home_team.name} vs {fixture.away_team.name}")
                print(f"    🏆 {flag} {league_name} - {time_str}")
                print()
            
            # Offer to analyze a specific match
            print(f"🎯 Vuoi analizzare una partita specifica?")
            choice = input(f"Inserisci il numero della partita (1-{len(all_fixtures)}, o 'n' per continuare): ").strip()
            
            if choice.isdigit() and 1 <= int(choice) <= len(all_fixtures):
                selected_idx = int(choice) - 1
                selected_fixture, league_name, flag, round_number = all_fixtures[selected_idx]
                
                print(f"\n🔍 Analizzando: {selected_fixture.home_team.name} vs {selected_fixture.away_team.name}")
                await self.analyze_single_fixture(selected_fixture, "Europe", league_name)
            elif choice.lower() not in ['n', 'no']:
                print("❌ Numero non valido")
        else:
            print("❌ Nessuna partita trovata in tutte le coppe")


async def run_interactive_menu():
    """Main entry point for interactive menu."""
    from cli.main_menu import run_main_menu
    await run_main_menu()
