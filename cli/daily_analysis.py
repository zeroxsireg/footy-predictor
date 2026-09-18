"""
Daily League Analysis CLI Module.

Handles the command-line interface for daily league analysis including:
- League selection wizard
- Single/Batch analysis execution
- Delegation to filters and report exporters
"""

import asyncio
from typing import Optional, Tuple

from core.config import get_settings
from core.daily_analyzer import DailyLeagueAnalyzer
from cli.daily_display import DailyAnalysisDisplayer
from adapters.football_api import FootballAPIClient
from config.leagues import get_league_manager
from cli.daily.report_exporter import DailyReportExporter
from cli.daily.advanced_filters import DailyAdvancedFilters
from cli.daily.batch_runner import DailyBatchRunner


class DailyLeagueAnalysisCLI:
    """CLI interface for daily league analysis (orchestrator)."""

    def __init__(self):
        self.analyzer = DailyLeagueAnalyzer()
        self.displayer = DailyAnalysisDisplayer()
        self.league_manager = get_league_manager()
        self.exporter = DailyReportExporter()
        self.batch_runner = DailyBatchRunner(self.analyzer, self.displayer, self.league_manager)

        # Build available leagues from enabled leagues (excluding cups)
        self.available_leagues = {}
        idx = 1
        for league in self.league_manager.get_enabled_leagues():
            if not league.is_cup:
                self.available_leagues[str(idx)] = (
                    league.country,
                    league.name,
                    league.flag,
                    league.country,
                )
                idx += 1

        self.special_options = {
            "all": "Tutti i campionati abilitati",
            "cups": "Tutte le coppe europee",
        }

    async def run(self):
        """Run the daily league analysis CLI."""
        print("\n" + "=" * 60)
        print("🏆 FOOTY PREDICTOR - ANALISI GIORNATA COMPLETA")
        print("=" * 60)
        print("🎯 Analizza tutte le partite della prossima giornata")
        print("📊 Statistiche avanzate, probabilità e picks ottimali")
        print("💡 Include quote bookmaker reali ed Expected Value")

        while True:
            try:
                selected_league = self._select_league()
                if not selected_league:
                    print("\n👋 Uscita dall'analisi giornaliera")
                    break

                if selected_league == "all":
                    await self.batch_runner.run_all_leagues_analysis()
                    continue
                elif selected_league == "cups":
                    await self.batch_runner.run_all_cups_analysis()
                    continue

                country, league_name, flag, country_it = selected_league
                if not self._confirm_analysis(country, league_name, flag, country_it):
                    continue

                print(f"\n⏳ Avvio analisi per {flag} {country_it} {league_name}...")
                print("⏱️  Questa operazione potrebbe richiedere alcuni minuti...")

                analysis = await self.analyzer.analyze_league_matchday(
                    country=country,
                    league_name=league_name,
                    country_flag=flag,
                    country_it=country_it,
                    season=get_settings().default_season,
                )

                self.displayer.display_daily_analysis(analysis)
                self.exporter.offer_save_results(analysis)

                cont = input("\n🔄 Vuoi analizzare un altro campionato? (s/n): ").strip().lower()
                if cont not in ["s", "si", "y", "yes"]:
                    print("\n👋 Grazie per aver usato Footy Predictor!")
                    break

            except KeyboardInterrupt:
                print("\n\n👋 Operazione interrotta dall'utente. Arrivederci!")
                break
            except Exception as e:
                print(f"\n❌ Errore durante l'analisi: {e}")
                retry = input("🔄 Vuoi riprovare? (s/n): ").strip().lower()
                if retry not in ["s", "si", "y", "yes"]:
                    break

    def _select_league(self) -> Optional[Tuple[str, str, str, str]]:
        """Prompt user to select a league from available options."""
        print("\n📋 SELEZIONA CAMPIONATO:")
        print("-" * 30)

        for key, (_, league_name, flag, country_it) in self.available_leagues.items():
            print(f"{key}. {flag} {country_it} - {league_name}")

        print("\n🎯 OPZIONI SPECIALI:")
        print("-" * 30)
        print("A. 🚀 Tutti i campionati abilitati (analisi completa)")
        print("C. 🏆 Tutte le coppe europee (Champions + Europa League)")
        print("0. 🚪 Torna al menu principale")

        while True:
            try:
                choice = input("\n🎯 Scelta: ").strip().upper()
                if choice == "0":
                    return None
                elif choice == "A":
                    return "all"
                elif choice == "C":
                    return "cups"
                elif choice in self.available_leagues:
                    return self.available_leagues[choice]
                else:
                    print("❌ Scelta non valida. Riprova.")
            except KeyboardInterrupt:
                return None

    def _confirm_analysis(self, country: str, league_name: str, flag: str, country_it: str) -> bool:
        """Confirm analysis execution with user."""
        print(f"\n🎯 CONFERMA ANALISI")
        print("-" * 30)
        print(f"🏆 Campionato: {flag} {country_it} - {league_name}")
        print(f"⏱️  Tempo stimato: 1-2 minuti")
        print(f"📊 Include: Statistiche complete, quote, picks ed EV")

        while True:
            try:
                confirm = input(f"\n🚀 Avviare l'analisi? (s/n): ").strip().lower()
                if confirm in ["s", "si", "y", "yes"]:
                    return True
                elif confirm in ["n", "no"]:
                    print("❌ Analisi annullata")
                    return False
                else:
                    print("❌ Risposta non valida. Usa 's' per sì o 'n' per no.")
            except KeyboardInterrupt:
                print("\n❌ Analisi annullata")
                return False

    # Facade methods for full backward compatibility
    def _offer_save_results(self, analysis):
        self.exporter.offer_save_results(analysis)

    def _save_results_to_file(self, analysis):
        self.exporter.save_results_to_file(analysis)

    def _generate_file_content(self, analysis) -> str:
        return self.exporter.generate_file_content(analysis)

    async def _run_all_leagues_analysis(self):
        await self.batch_runner.run_all_leagues_analysis()

    async def _run_all_cups_analysis(self):
        await self.batch_runner.run_all_cups_analysis()

    async def _show_advanced_menu(self, all_analyses):
        await DailyAdvancedFilters.show_advanced_menu(all_analyses)

    async def _filter_by_match_day(self, all_analyses):
        await DailyAdvancedFilters.filter_by_match_day(all_analyses)

    async def _filter_by_category(self, all_analyses):
        await DailyAdvancedFilters.filter_by_category(all_analyses)

    def _get_pick_category(self, pick):
        return DailyAdvancedFilters.get_pick_category(pick)


async def run_daily_league_analysis():
    """Entry point for daily league analysis."""
    cli = DailyLeagueAnalysisCLI()
    await cli.run()
