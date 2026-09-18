"""TTL per tipo di dato (SSOT condiviso da Redis e SQLite)."""

from typing import Optional

# TTL Configuration (in seconds). -1 = non scade mai.
TTL_CONFIG = {
    'roster': 30 * 24 * 3600,        # 30 giorni - roster cambiano raramente
    'team_stats': -1,                 # MAI SCADONO - statistiche squadre (dati storici)
    'shots_corners': -1,              # MAI SCADONO - shots/corners (dati storici)
    'historical_data': -1,            # Mai scadono - dati storici
    'finished_matches': -1,           # Mai scadono - partite finite
    'league_standings': 24 * 3600,    # 1 giorno - classifiche (cambiano)
    'live_odds': 30 * 60,             # 30 minuti - quote live
    'upcoming_fixtures': 6 * 3600,    # 6 ore - prossime partite
    'league_players_all': 24 * 3600,  # 24 ore per tutti i giocatori del campionato
    'team_metadata': -1,              # Mai scadono - metadati squadre
    'data_update': -1,                # Mai scadono - timestamp aggiornamenti
}

DEFAULT_TTL_SECONDS = 3600  # tipo sconosciuto: 1 ora


def ttl_seconds(ttl_type: Optional[str]) -> int:
    """TTL in secondi per un ttl_type (-1 = permanente)."""
    return TTL_CONFIG.get(ttl_type, DEFAULT_TTL_SECONDS)
