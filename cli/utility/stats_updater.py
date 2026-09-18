"""
Stats Updater module for Utility CLI.

Handles updating team and player statistics.
"""

from typing import List, Dict, Any


class UtilityStatsUpdater:
    """Handles team and player statistics update operations."""

    def __init__(self, api_client, data_service, enabled_leagues, current_season):
        self.api_client = api_client
        self.data_service = data_service
        self.enabled_leagues = enabled_leagues
        self.current_season = current_season

    async def update_team_statistics(self, cache_manager):
        """Aggiorna le statistiche delle squadre."""
        print("\n📊 AGGIORNAMENTO STATISTICHE SQUADRE")
        print("-" * 40)

        try:
            print("\nCampionati disponibili:")
            for idx, league in enumerate(self.enabled_leagues, 1):
                teams = await self.api_client.get_teams(
                    league.country, league.name, self.current_season, league.api_league_id
                )
                team_ids = [t.id for t in teams] if teams else []
                status = self.data_service.get_league_status_text(team_ids, "stats")
                print(f"{idx}. {league.flag} {league.name}{status}")

            print(f"{len(self.enabled_leagues) + 1}. 🌍 Aggiorna tutte le leghe")

            choice = input(f"\nScegli (1-{len(self.enabled_leagues) + 1}, 0 per tornare): ").strip()
            if choice == "0":
                return
            elif choice == str(len(self.enabled_leagues) + 1):
                await cache_manager.update_all_leagues_smart("stats", stats_updater=self)
            else:
                try:
                    idx = int(choice) - 1
                    if 0 <= idx < len(self.enabled_leagues):
                        league = self.enabled_leagues[idx]
                        await self.update_stats_for_league(league)
                    else:
                        print("❌ Scelta non valida.")
                        return
                except ValueError:
                    print("❌ Inserisci un numero valido.")
                    return

            print("\n✅ Aggiornamento statistiche completato!")
        except Exception as e:
            print(f"\n❌ Errore durante l'aggiornamento statistiche: {e}")

        input("\nPremi INVIO per continuare...")

    async def update_stats_for_league(self, league) -> bool:
        """Aggiorna le statistiche per una specifica lega."""
        print(f"\n🔄 Aggiornamento statistiche per {league.name}...")

        try:
            teams = await self.api_client.get_teams(
                league.country, league.name, self.current_season, league.api_league_id
            )
            if not teams:
                print(f"❌ Nessuna squadra trovata per {league.name}")
                return False

            updated_count = 0
            skipped_count = 0

            for team in teams:
                try:
                    should_update, reason = self.data_service.should_update_team(team.id, "stats")
                    if not should_update:
                        print(f"  ⏭️  {team.name}")
                        skipped_count += 1
                        continue

                    print(f"  🔄 {team.name}")
                    success = await self.api_client.force_update_team_statistics(
                        team.id, league.api_league_id, self.current_season
                    )

                    if success:
                        await self.data_service.mark_team_updated(team.id, "stats")
                        updated_count += 1
                        print(f"  ✅ {team.name}")
                    else:
                        print(f"  ❌ {team.name}: Aggiornamento fallito")
                except Exception as e:
                    print(f"  ❌ {team.name}: {e}")

            print(f"\n✅ Aggiornate {updated_count}/{len(teams)} statistiche per {league.name}")
            if skipped_count > 0:
                print(f"⏭️  Saltate {skipped_count} statistiche già aggiornate")
            return updated_count > 0 or skipped_count > 0
        except Exception as e:
            print(f"❌ Errore per {league.name}: {e}")
            return False

    async def update_player_statistics(self):
        """Aggiorna le statistiche dei giocatori."""
        print("\n⚽ AGGIORNAMENTO STATISTICHE GIOCATORI")
        print("-" * 40)
        print("💡 NOTA: Le statistiche giocatori vengono aggiornate automaticamente")
        print("         quando si aggiornano i roster delle squadre.")
        input("\nPremi INVIO per continuare...")
