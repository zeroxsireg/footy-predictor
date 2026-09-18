"""
Utility Menu CLI Module.

Interactive CLI menu for background data synchronization, roster updates,
team statistics caching and cache inspection.
"""

import asyncio

from adapters.football_api import FootballAPIClient
from utils.redis_cache import get_redis_cache
from services.data_service import DataService
from config.leagues import get_league_manager
from cli.utility.cache_manager import UtilityCacheManager
from cli.utility.roster_updater import UtilityRosterUpdater
from cli.utility.stats_updater import UtilityStatsUpdater


class UtilityMenuCLI:
    """Controller for data management and utility operations."""

    def __init__(self):
        self.api_client = FootballAPIClient()
        self.redis_cache = get_redis_cache()
        self.data_service = DataService(self.redis_cache)
        self.league_manager = get_league_manager()
        self.current_season = self.data_service.current_season

        self.enabled_leagues = self.league_manager.get_enabled_leagues()
        print(f"✅ Loaded {len(self.enabled_leagues)} enabled leagues")
        for league in self.enabled_leagues:
            print(f"   {league.flag} {league.name}")

        self.cache_mgr = UtilityCacheManager(
            self.redis_cache, self.api_client, self.data_service, self.enabled_leagues, self.current_season
        )
        self.roster_updater = UtilityRosterUpdater(
            self.api_client, self.data_service, self.enabled_leagues, self.current_season
        )
        self.stats_updater = UtilityStatsUpdater(
            self.api_client, self.data_service, self.enabled_leagues, self.current_season
        )

    async def run(self):
        """Esegue il menu utility principale."""
        await self.data_service.load_from_redis()

        while True:
            try:
                await self._show_main_menu()
                choice = input("\n🎯 Scegli un'opzione (0-6): ").strip()

                if choice == "0":
                    print("\n👋 Arrivederci!")
                    break
                elif choice == "1":
                    await self.roster_updater.update_team_rosters(self.cache_mgr)
                elif choice == "2":
                    await self.stats_updater.update_team_statistics(self.cache_mgr)
                elif choice == "3":
                    await self.stats_updater.update_player_statistics()
                elif choice == "4":
                    await self._update_markets_odds()
                elif choice == "5":
                    await self.cache_mgr.clear_all_cache()
                elif choice == "6":
                    await self.cache_mgr.show_cache_status()
                else:
                    print("❌ Opzione non valida. Riprova.")
                    input("\nPremi INVIO per continuare...")

            except KeyboardInterrupt:
                print("\n\n👋 Operazione interrotta. Arrivederci!")
                break
            except Exception as e:
                print(f"\n❌ Errore imprevisto: {e}")
                input("\nPremi INVIO per continuare...")

    async def _show_main_menu(self):
        """Mostra il menu principale utility."""
        print("\n" + "=" * 60)
        print("🔧 MENU UTILITY - AGGIORNAMENTO DATI")
        print("=" * 60)
        print("1. 📋 Aggiorna Roster Squadre")
        print("2. 📊 Aggiorna Statistiche Squadre")
        print("3. ⚽ Aggiorna Statistiche Giocatori")
        print("4. 💰 Aggiorna Mercati e Quote")
        print("5. 🗑️  Svuota Cache Completo")
        print("6. 📈 Stato Cache")
        print("0. 🚪 Esci")
        print("=" * 60)

    async def _update_markets_odds(self):
        """Aggiorna i mercati e le quote."""
        print("\n💰 AGGIORNAMENTO MERCATI E QUOTE")
        print("-" * 40)
        print("💡 I mercati e le quote vengono già aggiornati automaticamente durante le analisi.")
        input("\nPremi INVIO per continuare...")

    # Facade backward compatibility methods
    async def _update_team_rosters(self):
        await self.roster_updater.update_team_rosters(self.cache_mgr)

    async def _update_roster_for_league(self, league):
        return await self.roster_updater.update_roster_for_league(league)

    async def _update_team_statistics(self):
        await self.stats_updater.update_team_statistics(self.cache_mgr)

    async def _update_stats_for_league(self, league):
        return await self.stats_updater.update_stats_for_league(league)

    async def _update_player_statistics(self):
        await self.stats_updater.update_player_statistics()

    async def _clear_all_cache(self):
        await self.cache_mgr.clear_all_cache()

    async def _show_cache_status(self):
        await self.cache_mgr.show_cache_status()

    async def _update_all_leagues_smart(self, data_type: str):
        await self.cache_mgr.update_all_leagues_smart(
            data_type, roster_updater=self.roster_updater, stats_updater=self.stats_updater
        )


async def main():
    """Funzione principale per eseguire il menu utility."""
    utility_menu = UtilityMenuCLI()
    await utility_menu.run()


if __name__ == "__main__":
    asyncio.run(main())