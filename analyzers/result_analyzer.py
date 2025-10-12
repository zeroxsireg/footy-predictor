"""
Result Analyzer - Analisi risultato partita (1X2).

Responsabile di:
- Match Result (1 = Home Win, X = Draw, 2 = Away Win)
"""

from typing import List
from .base import BaseAnalyzer
from core.models import TeamStats
from core.betting_models import BettingRecommendation


class ResultAnalyzer(BaseAnalyzer):
    """Analyzer dedicato al mercato RISULTATO FINALE (1X2)."""
    
    def get_required_stats(self) -> List[str]:
        """Statistiche necessarie per analisi risultato."""
        return [
            'recent_form_points',
            'goal_difference_per_game',
            'wins',
            'draws',
            'losses',
            'matches_played'
        ]
    
    def analyze(self, home_stats: TeamStats, away_stats: TeamStats, **kwargs) -> List[BettingRecommendation]:
        """
        Genera raccomandazione per il risultato finale (1X2).
        
        Restituisce SOLO il risultato più probabile, non tutti e 3.
        
        Returns:
            Lista con UN SOLO pronostico (il più probabile)
        """
        if not self._validate_stats(home_stats, away_stats):
            return []
        
        # Calcola forza delle squadre
        home_form = home_stats.recent_form_points
        away_form = away_stats.recent_form_points
        
        home_goal_diff = home_stats.goal_difference_per_game
        away_goal_diff = away_stats.goal_difference_per_game
        
        # Percentuali vittoria/pareggio/sconfitta storiche
        home_win_pct = (home_stats.wins / home_stats.matches_played * 100) if home_stats.matches_played > 0 else 33
        home_draw_pct = (home_stats.draws / home_stats.matches_played * 100) if home_stats.matches_played > 0 else 33
        away_win_pct = (away_stats.wins / away_stats.matches_played * 100) if away_stats.matches_played > 0 else 33
        
        # 1. Home Win (1)
        home_win_prob = min(85, max(15, 
            40 +  # Base probability casa
            (home_form - away_form) * 5 +  # Forma recente
            home_goal_diff * 10 +  # Goal difference
            (home_win_pct - 33) * 0.5  # Win percentage storica
        ))
        
        # 2. Draw (X)
        balance_score = abs(home_form - away_form) + abs(home_goal_diff - away_goal_diff) * 5
        draw_prob = min(40, max(10, 25 - balance_score * 2 + home_draw_pct * 0.3))
        
        # 3. Away Win (2)
        away_win_prob = min(85, max(15,
            40 +  # Base probability
            (away_form - home_form) * 5 +  # Forma recente
            away_goal_diff * 10 +  # Goal difference
            (away_win_pct - 33) * 0.5 -  # Win percentage storica
            5  # Penalità trasferta
        ))
        
        # Trova il risultato più probabile
        results = [
            ("1 (Home Win)", home_win_prob, f"{home_stats.team.name} favorita"),
            ("X (Draw)", draw_prob, "Squadre bilanciate"),
            ("2 (Away Win)", away_win_prob, f"{away_stats.team.name} favorita")
        ]
        
        # Ordina per probabilità e prendi il più alto
        results.sort(key=lambda x: x[1], reverse=True)
        best_result = results[0]
        
        # Restituisci SOLO se supera la soglia minima
        if best_result[1] >= self.LOW_CONFIDENCE:
            return [self._create_recommendation(
                market="Match Result",
                selection=best_result[0],
                probability=best_result[1],
                odds_range=None,  # Quote rimosse
                reasoning=f"{best_result[2]}: {best_result[1]:.1f}% di probabilità"
            )]
        
        return []

