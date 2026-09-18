"""
Roster Updater module for Utility CLI.

Handles fetching and updating team rosters and squad lists.
"""

from typing import List, Dict, Any


class UtilityRosterUpdater:
    """Handles team roster download and cache update operations."""

    def __init__(self, api_client, data_service, enabled_leagues, current_season):
        self.api_client = api_client
        self.data_service = data_service
        self.enabled_leagues = enabled_leagues
        self.current_season = current_season

    async def update_team_rosters(self, cache_manager):
        """Aggiorna i roster delle squadre."""
        print("\n📋 AGGIORNAMENTO ROSTER SQUADRE")
        print("-" * 40)

        try:
            print("\nCampionati disponibili:")
            for idx, league in enumerate(self.enabled_leagues, 1):
                teams = await self.api_client.get_teams(
                    league.country, league.name, self.current_season, league.api_league_id
                )
                team_ids = [t.id for t in teams] if teams else []
                status = self.data_service.get_league_status_text(team_ids, "roster")
                print(f"{idx}. {league.flag} {league.name}{status}")

            print(f"{len(self.enabled_leagues) + 1}. 🌍 Aggiorna tutte le leghe")

            choice = input(f"\nScegli (1-{len(self.enabled_leagues) + 1}, 0 per tornare): ").strip()
            if choice == "0":
                return
            elif choice == str(len(self.enabled_leagues) + 1):
                await cache_manager.update_all_leagues_smart("roster", roster_updater=self)
            else:
                try:
                    idx = int(choice) - 1
                    if 0 <= idx < len(self.enabled_leagues):
                        league = self.enabled_leagues[idx]
                        await self.update_roster_for_league(league)
                    else:
                        print("❌ Scelta non valida.")
                        return
                except ValueError:
                    print("❌ Inserisci un numero valido.")
                    return

            print("\n✅ Aggiornamento roster completato!")
        except Exception as e:
            print(f"\n❌ Errore durante l'aggiornamento roster: {e}")

        input("\nPremi INVIO per continuare...")

    async def update_roster_for_league(self, league) -> bool:
        """Aggiorna i roster per una specifica lega."""
        print(f"\n🔄 Aggiornamento roster per {league.name}...")

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
                    should_update, reason = self.data_service.should_update_team(team.id, "roster")
                    if not should_update:
                        print(f"  ⏭️  {team.name}")
                        skipped_count += 1
                        continue

                    print(f"  🔄 {team.name}")
                    roster = await self.api_client.get_team_squad(team.id, self.current_season)

                    if roster:
                        await self.data_service.mark_team_updated(team.id, "roster")
                        updated_count += 1
                        print(f"  ✅ {team.name} ({len(roster)} giocatori)")
                    else:
                        print(f"  ⚠️  {team.name}: Roster vuoto")
                except Exception as e:
                    print(f"  ❌ {team.name}: {e}")

            print(f"\n✅ Aggiornati {updated_count}/{len(teams)} roster per {league.name}")
            if skipped_count > 0:
                print(f"⏭️  Saltati {skipped_count} roster già aggiornati")
            return updated_count > 0 or skipped_count > 0
        except Exception as e:
            print(f"❌ Errore per {league.name}: {e}")
            return False
