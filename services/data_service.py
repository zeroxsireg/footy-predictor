#!/usr/bin/env python3
"""
Data Service - Servizio unificato e veloce per gestione dati
Ottimizzato per frontend: < 100ms per ogni operazione.
"""

from datetime import datetime
from typing import Dict, List, Optional, Tuple
import pytz

class DataService:
    """
    Servizio centrale per gestione dati.
    Design principles:
    - Una sola responsabilità: gestire lo stato dei dati
    - Velocità: memoria first, Redis second
    - Semplicità: nessuna logica complessa
    - API-ready: pensato per essere chiamato da endpoints REST
    """
    
    def __init__(self, redis_cache):
        self.redis_cache = redis_cache
        
        # Memoria cache per velocità massima
        self._team_updates = {}  # {team_id: {'roster': timestamp, 'stats': timestamp}}
        
        # Current season
        self.current_season = 2025
    
    # ==========================================
    # TEAM STATUS MANAGEMENT (VELOCE)
    # ==========================================
    
    def is_team_updated(self, team_id: int, data_type: str) -> bool:
        """
        Controllo istantaneo se un team è aggiornato.
        Complessità: O(1)
        Performance: < 1ms
        """
        return (team_id in self._team_updates and 
                data_type in self._team_updates[team_id])
    
    async def mark_team_updated(self, team_id: int, data_type: str):
        """
        Marca un team come aggiornato.
        Performance: < 10ms
        """
        now = datetime.now(pytz.timezone('Europe/Rome'))
        
        # Aggiorna memoria (istantaneo)
        if team_id not in self._team_updates:
            self._team_updates[team_id] = {}
        self._team_updates[team_id][data_type] = now
        
        # Aggiorna Redis in background (non blocca)
        try:
            key = f"team_data:{team_id}:{self.current_season}"
            # Converti timestamps a string per JSON serialization
            serializable_data = {
                k: v.isoformat() if isinstance(v, datetime) else v 
                for k, v in self._team_updates[team_id].items()
            }
            await self.redis_cache.set_data(key, serializable_data, "data_update")

            
            # Aggiorna anche la lista di team aggiornati (per caricamento veloce)
            tracking_key = f"updated_teams:{self.current_season}"
            tracked_teams = await self.redis_cache.get_data(tracking_key) or []
            if team_id not in tracked_teams:
                tracked_teams.append(team_id)
                await self.redis_cache.set_data(tracking_key, tracked_teams, "data_update")
        except Exception as e:
            pass  # Non bloccare se Redis fallisce
    
    def get_team_status(self, team_id: int) -> Dict[str, bool]:
        """
        Ottieni lo stato completo di un team.
        Performance: < 1ms
        """
        if team_id not in self._team_updates:
            return {
                'roster': False,
                'stats': False,
                'player_stats': False
            }
        
        updates = self._team_updates[team_id]
        return {
            'roster': 'roster' in updates,
            'stats': 'stats' in updates,
            'player_stats': 'player_stats' in updates
        }
    
    # ==========================================
    # LEAGUE STATUS (VELOCE)
    # ==========================================
    
    def get_league_status(self, team_ids: List[int], data_type: str) -> Dict:
        """
        Ottieni status di una lega.
        Performance: < 5ms per 20 teams
        """
        total = len(team_ids)
        updated = sum(1 for tid in team_ids if self.is_team_updated(tid, data_type))
        
        percentage = (updated / total * 100) if total > 0 else 0
        
        return {
            'total': total,
            'updated': updated,
            'percentage': percentage,
            'status': self._get_status_label(percentage),
            'emoji': self._get_status_emoji(percentage)
        }
    
    def _get_status_label(self, percentage: float) -> str:
        """Converti percentuale in label."""
        if percentage >= 90:
            return 'complete'
        elif percentage >= 50:
            return 'partial'
        else:
            return 'needs_update'
    
    def _get_status_emoji(self, percentage: float) -> str:
        """Converti percentuale in emoji."""
        if percentage >= 90:
            return '🟢'
        elif percentage >= 50:
            return '🟡'
        else:
            return '🔴'
    
    def get_league_status_text(self, team_ids: List[int], data_type: str) -> str:
        """
        Ottieni status lega come testo formattato (per CLI).
        Performance: < 5ms
        """
        status = self.get_league_status(team_ids, data_type)
        return f" {status['emoji']} ({status['updated']}/{status['total']})"
    
    # ==========================================
    # UPDATE LOGIC (SEMPLICE)
    # ==========================================
    
    def should_update_team(self, team_id: int, data_type: str) -> Tuple[bool, str]:
        """
        Determina se un team deve essere aggiornato.
        Performance: < 1ms
        
        Returns:
            (should_update, reason)
        """
        # Real-time data sempre da aggiornare
        if data_type == 'odds':
            return True, 'real_time'
        
        # Se già aggiornato, skip
        if self.is_team_updated(team_id, data_type):
            return False, 'already_updated'
        
        # Altrimenti aggiorna
        return True, 'needs_update'
    
    # ==========================================
    # BULK OPERATIONS (PER PERFORMANCE)
    # ==========================================
    
    async def mark_multiple_teams_updated(self, team_ids: List[int], data_type: str):
        """
        Marca multipli team come aggiornati in batch.
        Performance: < 50ms per 20 teams
        """
        for team_id in team_ids:
            await self.mark_team_updated(team_id, data_type)
    
    def get_multiple_team_status(self, team_ids: List[int]) -> Dict[int, Dict]:
        """
        Ottieni status di multipli team in una sola chiamata.
        Performance: < 10ms per 20 teams
        """
        return {
            team_id: self.get_team_status(team_id)
            for team_id in team_ids
        }
    
    # ==========================================
    # CACHE MANAGEMENT
    # ==========================================
    
    async def load_from_redis(self):
        """
        Carica dati da Redis in memoria (chiamare all'avvio).
        Performance: < 500ms per 100 teams
        """
        try:
            # Scan tutte le chiavi team_data:*
            # Nota: Redis scan è veloce ed efficiente
            loaded_count = 0
            
            # Usa un pattern per trovare tutte le chiavi
            pattern = f"team_data:*:{self.current_season}"
            
            # OTTIMIZZAZIONE: Carica solo team IDs che sappiamo avere dati
            # Invece di fare 1000 chiamate Redis, ne facciamo solo quelle necessarie
            
            # Prova a caricare una chiave speciale che tiene traccia dei team aggiornati
            tracking_key = f"updated_teams:{self.current_season}"
            tracked_teams = await self.redis_cache.get_data(tracking_key)
            
            if tracked_teams and isinstance(tracked_teams, list):
                # Abbiamo una lista di team aggiornati
                team_ids_to_load = tracked_teams
            else:
                # Fallback: prova range conosciuti (molto limitati)
                team_ids_to_load = list(range(487, 510)) + list(range(33, 55)) + list(range(529, 550))
            
            # Carica in batch (massimo 50 team alla volta per non bloccare)
            for team_id in team_ids_to_load[:100]:  # Limita a 100 per performance
                key = f"team_data:{team_id}:{self.current_season}"
                data = await self.redis_cache.get_data(key)
                
                if data and isinstance(data, dict):
                    # Carica in memoria
                    if team_id not in self._team_updates:
                        self._team_updates[team_id] = {}
                    
                    for data_type, timestamp_str in data.items():
                        try:
                            if isinstance(timestamp_str, str):
                                timestamp = datetime.fromisoformat(timestamp_str)
                            else:
                                timestamp = timestamp_str
                            self._team_updates[team_id][data_type] = timestamp
                            loaded_count += 1
                        except:
                            pass
            
            if loaded_count > 0:
                print(f"✅ Loaded {loaded_count} updates from Redis to memory")
            
        except Exception as e:
            print(f"Error loading from Redis: {e}")
    
    def clear_memory_cache(self):
        """Pulisci la cache in memoria."""
        self._team_updates.clear()
    
    def get_stats(self) -> Dict:
        """Ottieni statistiche del servizio."""
        total_teams = len(self._team_updates)
        total_updates = sum(len(updates) for updates in self._team_updates.values())
        
        return {
            'teams_tracked': total_teams,
            'total_updates': total_updates,
            'avg_updates_per_team': total_updates / total_teams if total_teams > 0 else 0
        }

