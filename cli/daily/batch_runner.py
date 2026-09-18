"""
Batch Runner for Daily Analysis.

Executes analysis across all enabled national leagues or all European cups.
"""

from typing import List, Any
from core.config import get_settings
from cli.daily.advanced_filters import DailyAdvancedFilters


class DailyBatchRunner:
    """Orchestrates batch matchday analysis across multiple competitions."""

    def __init__(self, analyzer, displayer, league_manager):
        self.analyzer = analyzer
        self.displayer = displayer
        self.league_manager = league_manager

    async def run_all_leagues_analysis(self):
        """Run analysis for all enabled national leagues."""
        print("\n🚀 ANALISI TUTTI I CAMPIONATI ABILITATI")
        print("=" * 50)

        confirm = input("\n🎯 Confermi l'analisi completa? (s/n): ").strip().lower()
        if confirm not in ["s", "si", "y", "yes"]:
            print("❌ Analisi annullata")
            return

        all_leagues = [
            (league.country, league.name, league.flag, league.country)
            for league in self.league_manager.get_enabled_leagues()
            if not league.is_cup
        ]

        all_analyses = []
        for country, league_name, flag, country_it in all_leagues:
            print(f"\n📊 Analizzando {flag} {league_name}...")
            try:
                analysis = await self.analyzer.analyze_league_matchday(
                    country=country,
                    league_name=league_name,
                    country_flag=flag,
                    country_it=country_it,
                    season=get_settings().default_season,
                )
                if analysis:
                    all_analyses.append(analysis)
                    print(f"✅ Completato: {analysis.total_matches_analyzed} partite, {analysis.total_picks_generated} picks")
                else:
                    print(f"⚠️ Nessuna partita trovata per {league_name}")
            except Exception as e:
                print(f"❌ Errore per {league_name}: {e}")

        if all_analyses:
            self._display_combined_summary(all_analyses)
            await DailyAdvancedFilters.show_advanced_menu(all_analyses)
        else:
            print("❌ Nessuna analisi completata con successo")

    async def run_all_cups_analysis(self):
        """Run analysis for all European cups."""
        print("\n🏆 ANALISI TUTTE LE COPPE EUROPEE")
        print("=" * 50)

        confirm = input("\n🎯 Confermi l'analisi completa? (s/n): ").strip().lower()
        if confirm not in ["s", "si", "y", "yes"]:
            print("❌ Analisi annullata")
            return

        all_cups = [
            (league.country, league.name, league.flag, league.country)
            for league in self.league_manager.get_enabled_leagues()
            if league.is_cup
        ]

        all_analyses = []
        for country, league_name, flag, country_it in all_cups:
            print(f"\n📊 Analizzando {flag} {league_name}...")
            try:
                analysis = await self.analyzer.analyze_league_matchday(
                    country=country,
                    league_name=league_name,
                    country_flag=flag,
                    country_it=country_it,
                    season=get_settings().default_season,
                )
                if analysis:
                    all_analyses.append(analysis)
                    print(f"✅ Completato: {analysis.total_matches_analyzed} partite, {analysis.total_picks_generated} picks")
                else:
                    print(f"⚠️ Nessuna partita trovata per {league_name}")
            except Exception as e:
                print(f"❌ Errore per {league_name}: {e}")

        if all_analyses:
            self._display_combined_summary(all_analyses)
            await DailyAdvancedFilters.show_advanced_menu(all_analyses)
        else:
            print("❌ Nessuna analisi completata con successo")

    def _display_combined_summary(self, all_analyses: List[Any]):
        """Display consolidated metrics and drill-down for batch analyses."""
        print(f"\n🎉 ANALISI COMPLETA COMPLETATA!")
        print(f"📊 {len(all_analyses)} campionati analizzati")
        total_matches = sum(a.total_matches_analyzed for a in all_analyses)
        total_picks = sum(a.total_picks_generated for a in all_analyses)
        print(f"⚽ {total_matches} partite totali")
        print(f"🎯 {total_picks} picks totali")

        for analysis in all_analyses:
            print(f"\n{analysis.country_flag} {analysis.league_name}:")
            print(f"   ⚽ {analysis.total_matches_analyzed} partite")
            print(f"   🎯 {analysis.total_picks_generated} picks")
            print(f"   📊 Confidenza media: {analysis.summary_stats.get('average_confidence', 0):.1f}%")

        print(f"\n📋 ANALISI DETTAGLIATA PER OGNI CAMPIONATO\n" + "-" * 50)
        try:
            for analysis in all_analyses:
                print(f"\n{'='*80}")
                print(f"🏆 ANALISI DETTAGLIATA - {analysis.country_flag} {analysis.league_name}")
                print(f"{'='*80}")
                self.displayer.display_daily_analysis(analysis)

                if analysis != all_analyses[-1]:
                    cont = input("\n⏭️ Continuare con il prossimo campionato? (s/n): ").strip().lower()
                    if cont not in ["s", "si", "y", "yes"]:
                        break
        except KeyboardInterrupt:
            print("\n⚠️ Visualizzazione interrotta dall'utente")
