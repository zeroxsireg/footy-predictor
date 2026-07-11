#!/usr/bin/env python3
"""
League Configuration - Sistema modulare per gestire le leghe
Facile da espandere aggiungendo nuove leghe.
"""

from typing import Dict, List
from dataclasses import dataclass

@dataclass
class LeagueConfig:
    """Configurazione di una lega."""
    key: str  # Chiave unica (es: 'serie_a')
    name: str  # Nome (es: 'Serie A')
    country: str  # Paese (es: 'Italy')
    country_code: str  # Codice paese (es: 'IT')
    flag: str  # Flag emoji
    api_league_id: int  # ID nell'API Football
    enabled: bool = True  # Se la lega è attiva
    is_cup: bool = False  # Se è una coppa europea (True) o campionato nazionale (False)
    priority: int = 1  # Priorità per ordinamento (1 = alta)


class LeagueManager:
    """Gestore centralizzato delle leghe."""
    
    def __init__(self):
        self._leagues = self._initialize_leagues()
    
    def _initialize_leagues(self) -> Dict[str, LeagueConfig]:
        """Inizializza le leghe disponibili."""
        return {
            'serie_a': LeagueConfig(
                key='serie_a',
                name='Serie A',
                country='Italy',
                country_code='IT',
                flag='🇮🇹',
                api_league_id=135,
                enabled=True,
                priority=1
            ),
            'premier_league': LeagueConfig(
                key='premier_league',
                name='Premier League',
                country='England',
                country_code='GB',
                flag='🏴󠁧󠁢󠁥󠁮󠁧󠁿',
                api_league_id=39,
                enabled=False,
                priority=2
            ),
            'la_liga': LeagueConfig(
                key='la_liga',
                name='La Liga',
                country='Spain',
                country_code='ES',
                flag='🇪🇸',
                api_league_id=140,
                enabled=False,
                priority=3
            ),
            # Le seguenti leghe sono disabilitate per ora
            # Possono essere riabilitate semplicemente cambiando enabled=True
            'bundesliga': LeagueConfig(
                key='bundesliga',
                name='Bundesliga',
                country='Germany',
                country_code='DE',
                flag='🇩🇪',
                api_league_id=78,
                enabled=False,  # ❌ DISABILITATA
                priority=4
            ),
            'champions_league': LeagueConfig(
                key='champions_league',
                name='Champions League',
                country='UEFA',
                country_code='EU',
                flag='🏆',
                api_league_id=2,
                enabled=False,  # ❌ Disabilitata
                is_cup=True,  # Coppa europea
                priority=10
            ),
            'europa_league': LeagueConfig(
                key='europa_league',
                name='Europa League',
                country='UEFA',
                country_code='EU',
                flag='🥈',
                api_league_id=3,
                enabled=False,  # ❌ Disabilitata
                is_cup=True,  # Coppa europea
                priority=11
            )
        }
    
    def get_league(self, key: str) -> LeagueConfig:
        """Ottieni configurazione di una lega."""
        return self._leagues.get(key)
    
    def get_enabled_leagues(self) -> List[LeagueConfig]:
        """Ottieni tutte le leghe abilitate, ordinate per priorità."""
        enabled = [league for league in self._leagues.values() if league.enabled]
        return sorted(enabled, key=lambda x: x.priority)
    
    def get_all_leagues(self) -> List[LeagueConfig]:
        """Ottieni tutte le leghe (anche disabilitate)."""
        return sorted(self._leagues.values(), key=lambda x: x.priority)
    
    def enable_league(self, key: str):
        """Abilita una lega."""
        if key in self._leagues:
            self._leagues[key].enabled = True
    
    def disable_league(self, key: str):
        """Disabilita una lega."""
        if key in self._leagues:
            self._leagues[key].enabled = False
    
    def add_league(self, config: LeagueConfig):
        """Aggiungi una nuova lega (per future espansioni)."""
        self._leagues[config.key] = config


# Istanza globale del manager
_league_manager = None

def get_league_manager() -> LeagueManager:
    """Ottieni l'istanza singleton del league manager."""
    global _league_manager
    if _league_manager is None:
        _league_manager = LeagueManager()
    return _league_manager

