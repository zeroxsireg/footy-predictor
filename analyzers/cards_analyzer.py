"""
Cards Analyzer - Analisi mercati legati ai cartellini.

Responsabile di:
- Total Cards (cartellini totali)
- Team Cards (cartellini per squadra)
- Player Cards (giocatori individuali) - DA IMPLEMENTARE DOPO
"""

from typing import List
from .base import BaseAnalyzer
from core.models import TeamStats
from core.betting_models import BettingRecommendation


class CardsAnalyzer(BaseAnalyzer):
    """Analyzer dedicato ai mercati CARTELLINI."""
    
    def get_required_stats(self) -> List[str]:
        """Statistiche necessarie per analisi cartellini."""
        return [
            'yellow_cards_per_game',
            'red_cards'
        ]
    
    def analyze(self, home_stats: TeamStats, away_stats: TeamStats, **kwargs) -> List[BettingRecommendation]:
        """
        Genera tutte le raccomandazioni legate ai cartellini.
        
        Returns:
            Lista combinata di Total Cards + Team Cards
        """
        if not self._validate_stats(home_stats, away_stats):
            return []
        
        recommendations = []
        
        # 1. Total Cards
        recommendations.extend(self._analyze_total_cards(home_stats, away_stats))
        
        # 2. Team Cards
        recommendations.extend(self._analyze_team_cards(home_stats, away_stats))
        
        return recommendations
    
    def _analyze_total_cards(self, home_stats: TeamStats, away_stats: TeamStats) -> List[BettingRecommendation]:
        """Analizza Total Cards (cartellini totali)."""
        recommendations = []
        
        home_cards_avg = home_stats.yellow_cards_per_game
        away_cards_avg = away_stats.yellow_cards_per_game
        total_cards_expected = home_cards_avg + away_cards_avg
        
        # Aggiungi contributo rossi (pesano di più)
        home_red_cards = home_stats.red_cards or 0
        away_red_cards = away_stats.red_cards or 0
        total_red_cards = home_red_cards + away_red_cards
        
        if home_stats.matches_played > 0:
            total_cards_expected += (total_red_cards / home_stats.matches_played) * 0.5
        
        # Soglie ottimizzate per includere partite normali
        thresholds = [
            (1.5, "1.20-1.40"),   # Molto basso
            (2.5, "1.30-1.60"),   # Basso
            (3.5, "1.40-1.80"),   # Medio-basso
            (4.5, "1.70-2.20"),   # Medio
            (5.5, "2.50-4.00"),   # Alto
            (6.5, "3.50-6.00")    # Molto alto
        ]
        
        # STRATEGIA OTTIMALE: Seleziona la soglia PIÙ ALTA con prob >= 60%
        best_threshold = None
        best_prob = 0
        
        for threshold, _ in thresholds:
            # Calcola probabilità per questa soglia
            if total_cards_expected >= threshold:
                prob = min(95, max(15, 50 + (total_cards_expected - threshold) * 15))
            else:
                prob = min(50, max(5, (total_cards_expected / threshold) * 40))
            
            # Cerca la soglia PIÙ ALTA con prob >= 60%
            if prob >= 60:
                if threshold > (best_threshold or 0):
                    best_threshold = threshold
                    best_prob = prob
        
        if best_threshold and best_prob >= self.LOW_CONFIDENCE:
            level = "Alto" if total_cards_expected >= 5 else "Medio" if total_cards_expected >= 4 else "Normale"
            recommendations.append(self._create_recommendation(
                market="Total Cards",
                selection=f"Over {best_threshold}",
                probability=best_prob,
                odds_range=None,  # Quote rimosse
                reasoning=f"{level} volume cartellini: {total_cards_expected:.1f} cards/match"
            ))
        
        return recommendations
    
    def _analyze_team_cards(self, home_stats: TeamStats, away_stats: TeamStats) -> List[BettingRecommendation]:
        """Analizza Team Cards (cartellini per squadra)."""
        recommendations = []
        
        home_cards_avg = home_stats.yellow_cards_per_game
        away_cards_avg = away_stats.yellow_cards_per_game
        
        # Home Team Cards (soglie utili, escluso 0.5 troppo scontato)
        home_thresholds = [
            (1.5, "1.60-2.20"),
            (2.5, "2.50-4.00")
        ]
        
        for threshold, odds in home_thresholds:
            # Formula più permissiva
            if home_cards_avg >= threshold:
                prob = min(90, max(25, 55 + (home_cards_avg - threshold) * 20))
            else:
                prob = min(50, max(10, (home_cards_avg / threshold) * 45))
            
            if prob >= self.LOW_CONFIDENCE:
                recommendations.append(self._create_recommendation(
                    market=f"{home_stats.team.name} Cards",
                    selection=f"Over {threshold}",
                    probability=prob,
                    odds_range=odds,
                    reasoning=f"{home_stats.team.name}: {home_cards_avg:.2f} cards/match"
                ))
        
        # Away Team Cards (soglie utili, escluso 0.5 troppo scontato)
        away_thresholds = [
            (1.5, "1.80-2.40"),
            (2.5, "2.50-4.00")
        ]
        
        for threshold, odds in away_thresholds:
            # Formula più permissiva
            if away_cards_avg >= threshold:
                prob = min(90, max(25, 55 + (away_cards_avg - threshold) * 20))
            else:
                prob = min(50, max(10, (away_cards_avg / threshold) * 45))
            
            if prob >= self.LOW_CONFIDENCE:
                recommendations.append(self._create_recommendation(
                    market=f"{away_stats.team.name} Cards",
                    selection=f"Over {threshold}",
                    probability=prob,
                    odds_range=odds,
                    reasoning=f"{away_stats.team.name}: {away_cards_avg:.2f} cards/match in trasferta"
                ))
        
        return recommendations

