"""
Cache Manager module for Utility CLI.

Handles Redis cache inspection, clearing, smart multi-league update checks.
"""

from datetime import datetime
from typing import Dict, List, Any


class UtilityCacheManager:
    """Manages Redis cache operations and status inspection."""

    def __init__(self, redis_cache, api_client, data_service, enabled_leagues, current_season):
        self.redis_cache = redis_cache
        self.api_client = api_client
        self.data_service = data_service
        self.enabled_leagues = enabled_leagues
        self.current_season = current_season

    async def clear_all_cache(self):
        """Svuota completamente la cache Redis."""
        print("\n🗑️  SVUOTA CACHE COMPLETO")
        print("-" * 40)
        print("⚠️  Questa operazione rimuoverà TUTTI i dati dalla cache.")
        print("I dati verranno ricaricati automaticamente al prossimo utilizzo.")

        confirm = input("\nSei sicuro di voler procedere? (s/n): ").strip().lower()
        if confirm != "s":
            return

        try:
            print("\n🔄 Svuotamento cache in corso...")
            await self.redis_cache.clear_all_cache()
            print("✅ Cache svuotata completamente!")
            print("💡 I dati verranno ricaricati automaticamente al prossimo utilizzo.")
        except Exception as e:
            print(f"\n❌ Errore durante lo svuotamento cache: {e}")

        input("\nPremi INVIO per continuare...")

    async def show_cache_status(self):
        """Mostra lo stato della cache."""
        print("\n📈 STATO CACHE")
        print("-" * 40)

        try:
            cache_info = await self.redis_cache.get_cache_info()
            if cache_info:
                print(f"🔑 Chiavi totali in cache: {cache_info.get('total_keys', 'N/A')}")
                print(f"💾 Memoria utilizzata: {cache_info.get('used_memory', 'N/A')}")
                print(f"⏰ Uptime: {cache_info.get('uptime', 'N/A')}")
            else:
                print("❌ Impossibile ottenere informazioni sulla cache.")

            print("\n📋 Esempi di chiavi in cache:")
            sample_keys = await self.redis_cache.get_sample_keys(10)
            if sample_keys:
                for key in sample_keys:
                    print(f"  • {key}")
            else:
                print("  Nessuna chiave trovata.")
        except Exception as e:
            print(f"\n❌ Errore durante il recupero dello stato cache: {e}")

        input("\nPremi INVIO per continuare...")

    async def update_all_leagues_smart(self, data_type: str, roster_updater=None, stats_updater=None):
        """Aggiorna tutte le leghe INTELLIGENTE (salta quelle già complete)."""
        print(f"\n🌍 AGGIORNAMENTO TUTTE LE LEGHE - {data_type.upper()}")
        print("-" * 40)

        total_leagues = len(self.enabled_leagues)
        processed_leagues = 0
        skipped_leagues = 0

        for league in self.enabled_leagues:
            teams = await self.api_client.get_teams(
                league.country, league.name, self.current_season, league.api_league_id
            )

            if not teams:
                print(f"  ⚠️  {league.flag} {league.name}: Nessuna squadra trovata")
                continue

            team_ids = [t.id for t in teams]
            status = self.data_service.get_league_status(team_ids, data_type)

            if status["percentage"] >= 90:
                print(f"  ⏭️  {league.flag} {league.name}: Già aggiornata ({status['updated']}/{status['total']})")
                skipped_leagues += 1
                continue

            print(f"\n  🔄 {league.flag} {league.name} ({status['updated']}/{status['total']})...")
            if data_type == "roster" and roster_updater:
                await roster_updater.update_roster_for_league(league)
            elif data_type == "stats" and stats_updater:
                await stats_updater.update_stats_for_league(league)

            processed_leagues += 1

        print("\n" + "=" * 60)
        print("✅ Aggiornamento completato!")
        print(f"   Leghe aggiornate: {processed_leagues}/{total_leagues}")
        if skipped_leagues > 0:
            print(f"   Leghe saltate (già complete): {skipped_leagues}")
