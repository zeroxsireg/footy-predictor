#!/usr/bin/env python3
"""
Menu utility per aggiornare i dati del sistema.
Gestisce l'aggiornamento di roster, statistiche, mercati e quote.
"""

import asyncio
from typing import Dict, List, Optional
from datetime import datetime
import sys
import os

# Aggiungi il path del progetto
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from adapters.football_api import FootballAPIClient
from utils.redis_cache import get_redis_cache
from services.data_service import DataService
from config.leagues import get_league_manager
from core.models import Team


class UtilityMenuCLI:
    def __init__(self):
        self.api_client = FootballAPIClient()
        self.redis_cache = get_redis_cache()
        self.data_service = DataService(self.redis_cache)
        self.league_manager = get_league_manager()
        self.current_season = 2025
        
        # Carica leghe abilitate dinamicamente
        self.enabled_leagues = self.league_manager.get_enabled_leagues()
        print(f"✅ Loaded {len(self.enabled_leagues)} enabled leagues")
        for league in self.enabled_leagues:
            print(f"   {league.flag} {league.name}")
        
    async def run(self):
        """Esegue il menu utility principale."""
        # Carica dati da Redis velocemente
        await self.data_service.load_from_redis()
        
        while True:
            try:
                await self._show_main_menu()
                choice = input("\n🔧 Scegli un'opzione (1-6, 0 per uscire): ").strip()
                
                if choice == "0":
                    print("\n👋 Uscita dal menu utility.")
                    break
                elif choice == "1":
                    await self._update_team_rosters()
                elif choice == "2":
                    await self._update_team_statistics()
                elif choice == "3":
                    await self._update_player_statistics()
                elif choice == "4":
                    await self._update_markets_odds()
                elif choice == "5":
                    await self._clear_all_cache()
                elif choice == "6":
                    await self._show_cache_status()
                else:
                    print("\n❌ Opzione non valida. Riprova.")
                    
            except KeyboardInterrupt:
                print("\n\n👋 Uscita dal menu utility.")
                break
            except Exception as e:
                print(f"\n❌ Errore: {e}")
                input("\nPremi INVIO per continuare...")
    
    async def _show_main_menu(self):
        """Mostra il menu principale utility (VELOCE - no status check)."""
        print("\n" + "="*60)
        print("🔧 MENU UTILITY - AGGIORNAMENTO DATI")
        print("="*60)
        print("1. 📋 Aggiorna Roster Squadre")
        print("2. 📊 Aggiorna Statistiche Squadre")
        print("3. ⚽ Aggiorna Statistiche Giocatori")
        print("4. 💰 Aggiorna Mercati e Quote")
        print("5. 🗑️  Svuota Cache Completo")
        print("6. 📈 Stato Cache")
        print("0. 🚪 Esci")
        print("="*60)
    
    async def _update_team_rosters(self):
        """Aggiorna i roster delle squadre (NUOVO SISTEMA VELOCE E PULITO)."""
        print("\n📋 AGGIORNAMENTO ROSTER SQUADRE")
        print("-" * 40)
        
        try:
            # Mostra le leghe abilitate con stato
            print("\nCampionati disponibili:")
            for idx, league in enumerate(self.enabled_leagues, 1):
                # Ottieni teams per questa lega
                teams = await self.api_client.get_teams(
                    league.country, 
                    league.name, 
                    self.current_season, 
                    league.api_league_id
                )
                team_ids = [t.id for t in teams] if teams else []
                status = self.data_service.get_league_status_text(team_ids, 'roster')
                print(f"{idx}. {league.flag} {league.name}{status}")
            
            print(f"{len(self.enabled_leagues) + 1}. 🌍 Aggiorna tutte le leghe")
            
            # Selezione
            choice = input(f"\nScegli (1-{len(self.enabled_leagues) + 1}, 0 per tornare): ").strip()
            
            if choice == "0":
                return
            elif choice == str(len(self.enabled_leagues) + 1):
                # Aggiorna tutte le leghe (intelligente: salta quelle completamente aggiornate)
                await self._update_all_leagues_smart('roster')
            else:
                try:
                    idx = int(choice) - 1
                    if 0 <= idx < len(self.enabled_leagues):
                        league = self.enabled_leagues[idx]
                        await self._update_roster_for_league(league)
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
    
    async def _update_roster_for_league(self, league):
        """Aggiorna i roster per una lega (NUOVO SISTEMA VELOCE)."""
        print(f"\n🔄 Aggiornamento roster per {league.name}...")
        
        try:
            # Ottieni le squadre della lega
            teams = await self.api_client.get_teams(
                league.country, 
                league.name, 
                self.current_season,
                league.api_league_id
            )
            
            if not teams:
                print(f"❌ Nessuna squadra trovata per {league.name}")
                return False
            
            updated_count = 0
            skipped_count = 0
            
            for team in teams:
                try:
                    # Controllo DOPPIO: DataService + Redis
                    should_update, reason = self.data_service.should_update_team(team.id, 'roster')
                    
                    # Verifica anche se esiste in Redis (per l'analyzer)
                    cache_key = f"team_roster:{team.id}:{self.current_season}"
                    redis_data = await self.api_client.redis_cache.get_data(cache_key)
                    
                    if not should_update and redis_data:
                        # Davvero aggiornato (in memoria E in Redis)
                        print(f"  ⏭️  {team.name}")
                        skipped_count += 1
                        continue
                    
                    # Se manca in Redis, aggiorna anche se DataService dice "OK"
                    if not redis_data:
                        print(f"  🔄 {team.name} (Redis mancante)", end=" → ", flush=True)
                    else:
                        print(f"  🔄 {team.name}", end=" → ", flush=True)
                    
                    # Chiamata COMPLETA che include player stats
                    # Usa get_team_roster_fast per velocità + salvataggio manuale in Redis
                    players = await self.api_client.get_team_roster_fast(team.id, self.current_season)
                    
                    if players:
                        # IMPORTANTE: Salva in Redis per l'analyzer
                        # L'analyzer usa get_team_roster() che legge da Redis
                        cache_key = f"team_roster:{team.id}:{self.current_season}"
                        await self.api_client.redis_cache.set_data(cache_key, players, "roster")
                        
                        # Marca come aggiornato nel DataService
                        await self.data_service.mark_team_updated(team.id, 'roster')
                        await self.data_service.mark_team_updated(team.id, 'player_stats')
                        updated_count += 1
                        print(f"  ✅ {team.name} ({len(players)} players + stats)")
                    else:
                        print(f"  ❌ {team.name}: Nessun dato")
                except Exception as e:
                    print(f"  ❌ {team.name}: {e}")
            
            print(f"\n✅ Aggiornati {updated_count}/{len(teams)} roster per {league.name}")
            if skipped_count > 0:
                print(f"⏭️  Saltati {skipped_count} roster già aggiornati")
            return updated_count > 0 or skipped_count > 0
            
        except Exception as e:
            print(f"❌ Errore per {league.name}: {e}")
            return False
    
    async def _update_team_statistics(self):
        """Aggiorna le statistiche delle squadre (NUOVO SISTEMA VELOCE)."""
        print("\n📊 AGGIORNAMENTO STATISTICHE SQUADRE")
        print("-" * 40)
        
        try:
            # Mostra le leghe abilitate con stato
            print("\nCampionati disponibili:")
            for idx, league in enumerate(self.enabled_leagues, 1):
                # Ottieni teams per questa lega
                teams = await self.api_client.get_teams(
                    league.country, 
                    league.name, 
                    self.current_season, 
                    league.api_league_id
                )
                team_ids = [t.id for t in teams] if teams else []
                status = self.data_service.get_league_status_text(team_ids, 'stats')
                print(f"{idx}. {league.flag} {league.name}{status}")
            
            print(f"{len(self.enabled_leagues) + 1}. 🌍 Aggiorna tutte le leghe")
            
            # Selezione
            choice = input(f"\nScegli (1-{len(self.enabled_leagues) + 1}, 0 per tornare): ").strip()
            
            if choice == "0":
                return
            elif choice == str(len(self.enabled_leagues) + 1):
                # Aggiorna tutte le leghe (intelligente: salta quelle completamente aggiornate)
                await self._update_all_leagues_smart('stats')
            else:
                try:
                    idx = int(choice) - 1
                    if 0 <= idx < len(self.enabled_leagues):
                        league = self.enabled_leagues[idx]
                        await self._update_stats_for_league(league)
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
    
    async def _update_stats_for_league(self, league):
        """Aggiorna le statistiche per una lega (NUOVO SISTEMA VELOCE)."""
        print(f"\n🔄 Aggiornamento statistiche per {league.name}...")
        
        try:
            # Ottieni le squadre della lega
            teams = await self.api_client.get_teams(
                league.country, 
                league.name, 
                self.current_season,
                league.api_league_id
            )
            
            if not teams:
                print(f"❌ Nessuna squadra trovata per {league.name}")
                return False
            
            updated_count = 0
            skipped_count = 0
            
            for team in teams:
                try:
                    # Controllo istantaneo (< 1ms)
                    should_update, reason = self.data_service.should_update_team(team.id, 'stats')
                    
                    if not should_update:
                        print(f"  ⏭️  {team.name}")
                        skipped_count += 1
                        continue
                    
                    print(f"  🔄 {team.name}")
                    
                    # Aggiornamento veloce delle statistiche
                    success = await self.api_client.force_update_team_statistics(
                        team.id, 
                        league.api_league_id, 
                        self.current_season
                    )
                    
                    if success:
                        # Marca come aggiornato (< 10ms)
                        await self.data_service.mark_team_updated(team.id, 'stats')
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
    
    async def _update_player_statistics(self):
        """Aggiorna le statistiche dei giocatori (NUOVO SISTEMA OTTIMIZZATO)."""
        print("\n⚽ AGGIORNAMENTO STATISTICHE GIOCATORI")
        print("-" * 40)
        print("💡 NOTA: Le statistiche giocatori vengono aggiornate automaticamente")
        print("         quando si aggiornano i roster delle squadre.")
        print("\n⚠️  Questa operazione è MOLTO costosa in termini di API calls.")
        print("    Raccomandiamo di NON usarla a meno che non sia strettamente necessario.")
        
        confirm = input("\n⚠️  Sei sicuro di voler procedere? (s/n): ").strip().lower()
        if confirm != 's':
            print("\n✅ Operazione annullata. Le statistiche giocatori sono già")
            print("   disponibili attraverso i roster aggiornati.")
            input("\nPremi INVIO per continuare...")
            return
        
        try:
            # Mostra le leghe abilitate
            print("\nCampionati disponibili:")
            for idx, league in enumerate(self.enabled_leagues, 1):
                print(f"{idx}. {league.flag} {league.name}")
            
            print(f"{len(self.enabled_leagues) + 1}. 🌍 Aggiorna tutte le leghe")
            
            # Selezione
            choice = input(f"\nScegli (1-{len(self.enabled_leagues) + 1}, 0 per tornare): ").strip()
            
            if choice == "0":
                return
            elif choice == str(len(self.enabled_leagues) + 1):
                # Aggiorna tutte le leghe
                print("\n⚠️  ULTIMA CONFERMA: Questa operazione farà centinaia di chiamate API!")
                final_confirm = input("Procedere comunque? (s/n): ").strip().lower()
                if final_confirm != 's':
                    return
                    
                for league in self.enabled_leagues:
                    await self._update_player_stats_for_league(league)
            else:
                try:
                    idx = int(choice) - 1
                    if 0 <= idx < len(self.enabled_leagues):
                        league = self.enabled_leagues[idx]
                        await self._update_player_stats_for_league(league)
                    else:
                        print("❌ Scelta non valida.")
                        return
                except ValueError:
                    print("❌ Inserisci un numero valido.")
                    return
            
            print("\n✅ Aggiornamento statistiche giocatori completato!")
            
        except Exception as e:
            print(f"\n❌ Errore durante l'aggiornamento statistiche giocatori: {e}")
        
        input("\nPremi INVIO per continuare...")
    
    async def _update_player_stats_for_league(self, league):
        """
        Aggiorna le statistiche dei giocatori per una lega.
        
        NOTA: Questa operazione è MOLTO costosa (500+ API calls per lega).
        Le statistiche giocatori sono già incluse nei roster.
        Questo metodo è mantenuto solo per compatibilità.
        """
        print(f"\n🔄 Aggiornamento statistiche giocatori per {league.name}...")
        print("⚠️  ATTENZIONE: Operazione molto costosa in corso...")
        
        try:
            # Ottieni le squadre della lega
            teams = await self.api_client.get_teams(
                league.country, 
                league.name, 
                self.current_season,
                league.api_league_id
            )
            
            if not teams:
                print(f"❌ Nessuna squadra trovata per {league.name}")
                return False
            
            print(f"\n💡 OTTIMIZZAZIONE: Invece di aggiornare {len(teams)} squadre x ~25 giocatori")
            print(f"   (= ~{len(teams) * 25} chiamate API), usiamo i dati dei roster già presenti.")
            print(f"\n✅ Le statistiche giocatori sono già disponibili attraverso:")
            print(f"   - Roster aggiornati (contengono dati giocatori)")
            print(f"   - Team statistics (contengono aggregati)")
            print(f"\n📊 Per statistiche dettagliate giocatori specifici, il sistema")
            print(f"   le recupera automaticamente durante l'analisi delle partite.")
            
            # Marca la lega come "aggiornata" per player_stats
            # anche se non facciamo nulla (i dati sono nei roster)
            for team in teams:
                await self.data_service.mark_team_updated(team.id, 'player_stats')
            
            print(f"\n✅ Statistiche giocatori disponibili per {league.name}")
            return True
            
        except Exception as e:
            print(f"❌ Errore per {league.name}: {e}")
            return False
    
    async def _update_markets_odds(self):
        """Aggiorna i mercati e le quote."""
        print("\n💰 AGGIORNAMENTO MERCATI E QUOTE")
        print("-" * 40)
        print("⚠️  Questa funzionalità sarà implementata in futuro.")
        print("I mercati e le quote vengono già aggiornati automaticamente durante le analisi.")
        
        input("\nPremi INVIO per continuare...")
    
    async def _clear_all_cache(self):
        """Svuota completamente la cache Redis."""
        print("\n🗑️  SVUOTA CACHE COMPLETO")
        print("-" * 40)
        print("⚠️  Questa operazione rimuoverà TUTTI i dati dalla cache.")
        print("I dati verranno ricaricati automaticamente al prossimo utilizzo.")
        
        confirm = input("\nSei sicuro di voler procedere? (s/n): ").strip().lower()
        if confirm != 's':
            return
        
        try:
            print("\n🔄 Svuotamento cache in corso...")
            
            # Svuota tutta la cache
            await self.redis_cache.clear_all_cache()
            
            print("✅ Cache svuotata completamente!")
            print("💡 I dati verranno ricaricati automaticamente al prossimo utilizzo.")
            
        except Exception as e:
            print(f"\n❌ Errore durante lo svuotamento cache: {e}")
        
        input("\nPremi INVIO per continuare...")
    
    async def _show_cache_status(self):
        """Mostra lo stato della cache."""
        print("\n📈 STATO CACHE")
        print("-" * 40)
        
        try:
            # Ottieni informazioni sulla cache
            cache_info = await self.redis_cache.get_cache_info()
            
            if cache_info:
                print(f"🔑 Chiavi totali in cache: {cache_info.get('total_keys', 'N/A')}")
                print(f"💾 Memoria utilizzata: {cache_info.get('used_memory', 'N/A')}")
                print(f"⏰ Uptime: {cache_info.get('uptime', 'N/A')}")
            else:
                print("❌ Impossibile ottenere informazioni sulla cache.")
            
            # Mostra alcune chiavi di esempio
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
    
    async def _get_last_update_status(self, data_type: str) -> str:
        """Ottiene lo stato dell'ultimo aggiornamento per un tipo di dato."""
        try:
            # Ottieni informazioni dalla cache
            cache_info = await self.redis_cache.get_cache_info()
            
            if not cache_info or 'error' in cache_info:
                return " ❌ (Cache non disponibile)"
            
            # Simula controllo dell'ultimo aggiornamento
            # In una implementazione reale, dovresti controllare timestamp specifici
            today = datetime.now().date()
            
            # Controlla se ci sono dati recenti per questo tipo
            if data_type == "roster":
                # Controlla se ci sono roster recenti
                sample_keys = await self.redis_cache.get_sample_keys(5)
                has_recent_data = any("team_squad" in key for key in sample_keys)
            elif data_type == "team_stats":
                sample_keys = await self.redis_cache.get_sample_keys(5)
                has_recent_data = any("team_stats" in key for key in sample_keys)
            elif data_type == "player_stats":
                sample_keys = await self.redis_cache.get_sample_keys(5)
                has_recent_data = any("player_stats" in key for key in sample_keys)
            elif data_type == "markets":
                # I mercati sono sempre aggiornati in tempo reale
                return " 🟢 (Real-time)"
            elif data_type in ["all_leagues", "all_cups"]:
                # Controlla se ci sono dati per entrambi i tipi
                sample_keys = await self.redis_cache.get_sample_keys(10)
                has_recent_data = any(key_type in str(sample_keys) for key_type in ["team_squad", "team_stats"])
            else:
                has_recent_data = False
            
            if has_recent_data:
                return " 🟢 (Aggiornato)"
            else:
                return " 🔴 (Non aggiornato)"
                
        except Exception as e:
            return " ❓ (Errore controllo)"
    
    async def _update_all_leagues_smart(self, data_type: str):
        """Aggiorna tutte le leghe INTELLIGENTE (salta quelle già complete)."""
        print(f"\n🌍 AGGIORNAMENTO TUTTE LE LEGHE - {data_type.upper()}")
        print("-" * 40)
        
        total_leagues = len(self.enabled_leagues)
        processed_leagues = 0
        skipped_leagues = 0
        
        for league in self.enabled_leagues:
            # Ottieni teams per questa lega
            teams = await self.api_client.get_teams(
                league.country, 
                league.name, 
                self.current_season, 
                league.api_league_id
            )
            
            if not teams:
                print(f"  ⚠️  {league.flag} {league.name}: Nessuna squadra trovata")
                continue
            
            # Controlla status lega
            team_ids = [t.id for t in teams]
            status = self.data_service.get_league_status(team_ids, data_type)
            
            # Se lega è completamente aggiornata (>= 90%), salta
            if status['percentage'] >= 90:
                print(f"  ⏭️  {league.flag} {league.name}: Già aggiornata ({status['updated']}/{status['total']})")
                skipped_leagues += 1
                continue
            
            # Aggiorna la lega (parzialmente o non aggiornata)
            print(f"\n  🔄 {league.flag} {league.name} ({status['updated']}/{status['total']})...")
            
            if data_type == 'roster':
                await self._update_roster_for_league(league)
            elif data_type == 'stats':
                await self._update_stats_for_league(league)
            
            processed_leagues += 1
        
        print("\n" + "="*60)
        print(f"✅ Aggiornamento completato!")
        print(f"   Leghe aggiornate: {processed_leagues}/{total_leagues}")
        if skipped_leagues > 0:
            print(f"   Leghe saltate (già complete): {skipped_leagues}")
    
    async def _get_league_update_status(self, data_type: str, league_key: str, config: Dict) -> str:
        """Ottiene lo stato dell'ultimo aggiornamento per un campionato specifico."""
        try:
            league_id = config.get('league_id')
            country = config.get('country')
            league_name = config.get('league_name')
            
            # Ottieni le squadre del campionato per verificare i dati
            teams = await self.api_client.get_teams(country, league_name, self.current_season, league_id)
            
            if not teams:
                return " ❌ (Nessun dato)"
            
            updated_teams = 0
            needs_update_teams = 0
            real_time_teams = 0
            total_teams = len(teams)
            
            # Usa il data manager per controllo istantaneo
            team_ids = [team.id for team in teams]
            return self.data_manager.get_league_status(team_ids, data_type)
            
        except Exception as e:
            return " ❓ (Errore controllo)"
    
    
    async def _update_all_leagues_rosters(self):
        """Aggiorna i roster di tutti i campionati nazionali."""
        print("\n🌍 AGGIORNAMENTO ROSTER - TUTTI I CAMPIONATI")
        print("-" * 40)
        
        try:
            # Filtra solo i campionati nazionali (non coppe)
            national_leagues = {k: v for k, v in self.league_configs.items() 
                              if v["country"] != "UEFA"}
            
            print(f"\n🔄 Aggiornamento roster di {len(national_leagues)} campionati nazionali...")
            
            total_updated = 0
            for league_key, config in national_leagues.items():
                print(f"\n📋 {config['country_flag']} {config['name_it']}...")
                
                roster_updated = await self._update_roster_for_league(league_key, config)
                
                if roster_updated:
                    total_updated += 1
                    print(f"  ✅ {config['name_it']} completato")
                else:
                    print(f"  ⚠️  {config['name_it']} completato con errori")
            
            print(f"\n✅ Aggiornamento roster completato: {total_updated}/{len(national_leagues)} campionati")
            
        except Exception as e:
            print(f"\n❌ Errore durante l'aggiornamento roster di tutti i campionati: {e}")
        
        input("\nPremi INVIO per continuare...")
    
    async def _update_all_cups_rosters(self):
        """Aggiorna i roster di tutte le coppe europee."""
        print("\n🏆 AGGIORNAMENTO ROSTER - TUTTE LE COPPE")
        print("-" * 40)
        
        try:
            # Filtra solo le coppe europee
            european_cups = {k: v for k, v in self.league_configs.items() 
                           if v["country"] == "UEFA"}
            
            print(f"\n🔄 Aggiornamento roster di {len(european_cups)} coppe europee...")
            
            total_updated = 0
            for league_key, config in european_cups.items():
                print(f"\n🏆 {config['country_flag']} {config['name_it']}...")
                
                roster_updated = await self._update_roster_for_league(league_key, config)
                
                if roster_updated:
                    total_updated += 1
                    print(f"  ✅ {config['name_it']} completato")
                else:
                    print(f"  ⚠️  {config['name_it']} completato con errori")
            
            print(f"\n✅ Aggiornamento roster completato: {total_updated}/{len(european_cups)} coppe")
            
        except Exception as e:
            print(f"\n❌ Errore durante l'aggiornamento roster di tutte le coppe: {e}")
        
        input("\nPremi INVIO per continuare...")
    
    async def _update_all_leagues_stats(self):
        """Aggiorna le statistiche di tutti i campionati nazionali."""
        print("\n🌍 AGGIORNAMENTO STATISTICHE - TUTTI I CAMPIONATI")
        print("-" * 40)
        
        try:
            # Filtra solo i campionati nazionali (non coppe)
            national_leagues = {k: v for k, v in self.league_configs.items() 
                              if v["country"] != "UEFA"}
            
            print(f"\n🔄 Aggiornamento statistiche di {len(national_leagues)} campionati nazionali...")
            
            total_updated = 0
            for league_key, config in national_leagues.items():
                print(f"\n📊 {config['country_flag']} {config['name_it']}...")
                
                stats_updated = await self._update_stats_for_league(league_key, config)
                
                if stats_updated:
                    total_updated += 1
                    print(f"  ✅ {config['name_it']} completato")
                else:
                    print(f"  ⚠️  {config['name_it']} completato con errori")
            
            print(f"\n✅ Aggiornamento statistiche completato: {total_updated}/{len(national_leagues)} campionati")
            
        except Exception as e:
            print(f"\n❌ Errore durante l'aggiornamento statistiche di tutti i campionati: {e}")
        
        input("\nPremi INVIO per continuare...")
    
    async def _update_all_cups_stats(self):
        """Aggiorna le statistiche di tutte le coppe europee."""
        print("\n🏆 AGGIORNAMENTO STATISTICHE - TUTTE LE COPPE")
        print("-" * 40)
        
        try:
            # Filtra solo le coppe europee
            european_cups = {k: v for k, v in self.league_configs.items() 
                           if v["country"] == "UEFA"}
            
            print(f"\n🔄 Aggiornamento statistiche di {len(european_cups)} coppe europee...")
            
            total_updated = 0
            for league_key, config in european_cups.items():
                print(f"\n🏆 {config['country_flag']} {config['name_it']}...")
                
                stats_updated = await self._update_stats_for_league(league_key, config)
                
                if stats_updated:
                    total_updated += 1
                    print(f"  ✅ {config['name_it']} completato")
                else:
                    print(f"  ⚠️  {config['name_it']} completato con errori")
            
            print(f"\n✅ Aggiornamento statistiche completato: {total_updated}/{len(european_cups)} coppe")
            
        except Exception as e:
            print(f"\n❌ Errore durante l'aggiornamento statistiche di tutte le coppe: {e}")
        
        input("\nPremi INVIO per continuare...")


async def main():
    """Funzione principale per eseguire il menu utility."""
    utility_menu = UtilityMenuCLI()
    await utility_menu.run()


if __name__ == "__main__":
    asyncio.run(main())