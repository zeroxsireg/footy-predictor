"""
Player Cards Analyzer - Analisi cartellini giocatori individuali.

Responsabile di:
- Player Cards (giocatori specifici a rischio cartellino)

NOTA: Questo analyzer è temporaneamente DISABILITATO a causa di dati API inaffidabili.
Le statistiche giocatori sono cumulative (multi-stagione) e non filtrabili per stagione corrente.
Quando l'API fornirà dati season-specific, questo modulo sarà riattivato.
"""

from typing import List, Optional
from .base import BaseAnalyzer
from core.models import TeamStats, Fixture
from core.betting_models import BettingRecommendation
from core.daily_models import DailyPick


class PlayerCardsAnalyzer(BaseAnalyzer):
    """
    Analyzer dedicato ai CARTELLINI GIOCATORI INDIVIDUALI.
    
    STATO: TEMPORANEAMENTE DISABILITATO
    MOTIVO: Dati API cumulativi (non season-specific)
    """
    
    def __init__(self):
        super().__init__()
        self.enabled = True  # ABILITATO - dati disponibili in Redis
    
    def get_required_stats(self) -> List[str]:
        """Statistiche necessarie (quando sarà abilitato)."""
        return [
            'yellow_cards_per_game',
            'fouls_per_game'  # Se disponibile
        ]
    
    def analyze(self, home_stats: TeamStats, away_stats: TeamStats, **kwargs) -> List[BettingRecommendation]:
        """
        Analizza giocatori a rischio cartellino.
        
        Temporaneamente disabilitato - ritorna lista vuota.
        """
        if not self.enabled:
            return []
        
        # TODO: Implementare quando API fornirà dati season-specific
        return []
    
    async def analyze_match_players(self, fixture: Fixture, standings: List, 
                                   league_name: str, api_client) -> List[DailyPick]:
        """
        Analizza giocatori specifici per una partita.
        
        Logica basata su:
        1. Falli per 90 minuti (criterio principale)
        2. Cartellini per 90 minuti (conferma tendenza)
        3. Posizione (difensori/centrocampisti più a rischio)
        4. Solo giocatori con minuti > 0
        
        SPECIALE PER COPPE EUROPEE:
        - Usa statistiche del campionato nazionale (non della coppa)
        - Se squadra non nei top 5 campionati → SKIP
        
        Args:
            fixture: Partita da analizzare
            standings: Classifica (per contesto)
            league_name: Nome lega
            api_client: Client API
            
        Returns:
            Lista di DailyPick per giocatori (top 8)
        """
        if not self.enabled:
            return []
        
        try:
            from core.config import get_settings
            settings = get_settings()
            season = settings.default_season
            
            # NUOVO: Rileva se siamo in una coppa europea
            is_european_cup = league_name.lower() in ['champions league', 'europa league', 'conference league']
            
            if is_european_cup:
                # Per le coppe, SKIP player cards per ora
                # MOTIVO: Stats player sono aggregate (campionato + coppa) e non possiamo separarle
                # TODO: Implementare fetch stats filtrate per league_id nazionale
                print(f"   ⚠️  Player cards DISABILITATI per coppe europee")
                print(f"   💡 Stats player aggregate inquinerebbero le previsioni del campionato")
                return []
            
            # Get rosters from Redis cache (solo per campionati nazionali)
            home_roster = api_client.redis_cache.get_team_roster(fixture.home_team.id, season)
            away_roster = api_client.redis_cache.get_team_roster(fixture.away_team.id, season)
            
            if not home_roster and not away_roster:
                return []
            
            # Get team positions for context
            home_position = self._get_team_position(fixture.home_team.id, standings) if standings else None
            away_position = self._get_team_position(fixture.away_team.id, standings) if standings else None
            
            player_picks = []
            
            # Analyze home team players
            if home_roster:
                for player_data in home_roster:
                    if self._is_defensive_player(player_data):
                        card_probability = self._calculate_player_card_probability(
                            player_data, "home", home_position, away_position, fixture.away_team.name
                        )
                        
                        if card_probability >= 0.20:  # 20% minimum threshold
                            pick = DailyPick(
                                match_id=fixture.id,
                                home_team=fixture.home_team.name,
                                away_team=fixture.away_team.name,
                                market=f"Player Card - {player_data.get('name', 'Unknown')}",
                                selection="Yellow Card",
                                confidence="HIGH" if card_probability >= 0.55 else "MEDIUM" if card_probability >= 0.35 else "LOW",
                                percentage=card_probability * 100,
                                odds_range=None,  # Quote rimosse
                                reasoning=self._get_player_card_reasoning(player_data, "home", home_position, away_position),
                                match_time=fixture.date,
                                league=league_name,
                                real_odds=None,
                                bookmaker=None,
                                player_team=fixture.home_team.name
                            )
                            player_picks.append(pick)
            
            # Analyze away team players
            if away_roster:
                for player_data in away_roster:
                    if self._is_defensive_player(player_data):
                        card_probability = self._calculate_player_card_probability(
                            player_data, "away", away_position, home_position, fixture.home_team.name
                        )
                        
                        if card_probability >= 0.20:  # 20% minimum threshold
                            pick = DailyPick(
                                match_id=fixture.id,
                                home_team=fixture.home_team.name,
                                away_team=fixture.away_team.name,
                                market=f"Player Card - {player_data.get('name', 'Unknown')}",
                                selection="Yellow Card",
                                confidence="HIGH" if card_probability >= 0.55 else "MEDIUM" if card_probability >= 0.35 else "LOW",
                                percentage=card_probability * 100,
                                odds_range=None,  # Quote rimosse
                                reasoning=self._get_player_card_reasoning(player_data, "away", away_position, home_position),
                                match_time=fixture.date,
                                league=league_name,
                                real_odds=None,
                                bookmaker=None,
                                player_team=fixture.away_team.name
                            )
                            player_picks.append(pick)
            
            # Sort by probability and return top 8
            player_picks.sort(key=lambda p: p.percentage, reverse=True)
            return player_picks[:8]
            
        except Exception as e:
            print(f"⚠️  Player cards analysis failed: {e}")
            return []
    
    def enable(self):
        """Abilita l'analyzer quando dati API saranno affidabili."""
        self.enabled = True
        print("✅ Player Cards Analyzer abilitato")
    
    def disable(self):
        """Disabilita l'analyzer."""
        self.enabled = False
        print("⚠️  Player Cards Analyzer disabilitato")
    
    def _is_defensive_player(self, player_data: dict) -> bool:
        """Verifica se il giocatore è in posizione difensiva/centrocampo."""
        if not player_data:
            return False
        
        position = player_data.get('position', '')
        if not isinstance(position, str):
            return False
        
        position = position.lower()
        defensive_positions = [
            'defender', 'centre-back', 'left-back', 'right-back', 'wing-back',
            'defensive midfielder', 'midfielder', 'central midfielder'
        ]
        
        return any(pos in position for pos in defensive_positions)
    
    def _calculate_player_card_probability(self, player_data: dict, team_side: str,
                                          team_position: Optional[int], 
                                          opponent_position: Optional[int],
                                          opponent_name: str) -> float:
        """
        Calcola probabilità cartellino basata su falli/90min e cards/90min.
        """
        # Statistiche giocatore
        appearances = player_data.get('appearances') or 0
        minutes = player_data.get('minutes') or 0
        yellow_cards = player_data.get('yellow_cards') or 0
        fouls_committed = player_data.get('fouls_committed') or 0
        
        # Skip se mai giocato O pochi minuti (< 270 = ~3 partite complete)
        # Questo evita dati gonfiati e cross-team da giocatori con sample size troppo piccolo
        # NOTA: Dati API sono cumulativi (possono includere squadre/stagioni precedenti)
        if minutes == 0 or appearances == 0 or minutes < 270:
            return 0.0
        
        # Calcola per 90 minuti
        yellow_per_90 = (yellow_cards / minutes) * 90 if minutes > 0 else 0
        fouls_per_90 = (fouls_committed / minutes) * 90 if minutes > 0 else 0
        
        # Base probability da falli/90min (criterio principale)
        if fouls_per_90 >= 3.0:
            base_prob = 0.65
        elif fouls_per_90 >= 2.5:
            base_prob = 0.55
        elif fouls_per_90 >= 2.0:
            base_prob = 0.45
        elif fouls_per_90 >= 1.5:
            base_prob = 0.35
        else:
            base_prob = 0.20
        
        # Boost da cartellini/90min
        if yellow_per_90 >= 0.3:
            base_prob *= 1.3
        elif yellow_per_90 >= 0.15:
            base_prob *= 1.15
        
        # Boost posizione
        position = player_data.get('position', '').lower()
        if 'defender' in position or 'defensive' in position:
            base_prob *= 1.2
        elif 'midfielder' in position:
            base_prob *= 1.1
        
        return min(0.95, base_prob)
    
    def _get_team_position(self, team_id: int, standings: List) -> Optional[int]:
        """Ottiene posizione squadra in classifica."""
        if not standings:
            return None
        
        for standing in standings:
            if standing.get('team', {}).get('id') == team_id:
                return standing.get('rank')
        return None
    
    def _get_player_card_reasoning(self, player_data: dict, team_side: str,
                                   team_position: Optional[int],
                                   opponent_position: Optional[int]) -> str:
        """Genera reasoning per player card pick."""
        name = player_data.get('name', 'Player')
        position = player_data.get('position', 'Unknown')
        
        minutes = player_data.get('minutes') or 0
        yellow_cards = player_data.get('yellow_cards') or 0
        fouls = player_data.get('fouls_committed') or 0
        
        if minutes > 0:
            fouls_per_90 = (fouls / minutes) * 90
            cards_per_90 = (yellow_cards / minutes) * 90
            
            return f"{name} ({position}): {fouls_per_90:.1f} fouls/90min, {cards_per_90:.2f} cards/90min"
        
        return f"{name} ({position}): Defensive role, high risk"

