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
        """Analizza Total Cards (cartellini totali) con distribuzione di Poisson."""
        recommendations = []

        home_cards_avg = home_stats.yellow_cards_per_game
        away_cards_avg = away_stats.yellow_cards_per_game
        total_cards_expected = home_cards_avg + away_cards_avg

        # Contributo rossi: contano ~2 cartellini ciascuno
        total_matches = home_stats.matches_played or 1
        red_per_game = (home_stats.red_cards + away_stats.red_cards) / total_matches
        total_cards_expected += red_per_game * 2.0

        # Soglie standard per cartellini — cerca la più alta con prob >= 60%
        best_threshold = None
        best_prob = 0.0
        for threshold in [1.5, 2.5, 3.5, 4.5, 5.5, 6.5]:
            prob = self._poisson_over_prob(total_cards_expected, threshold) * 100
            if prob >= 60.0 and threshold > (best_threshold or 0):
                best_threshold = threshold
                best_prob = prob

        if best_threshold and best_prob >= self.LOW_CONFIDENCE:
            level = "Alto" if total_cards_expected >= 5 else "Medio" if total_cards_expected >= 4 else "Normale"
            recommendations.append(self._create_recommendation(
                market="Total Cards",
                selection=f"Over {best_threshold}",
                probability=best_prob,
                reasoning=f"{level} volume cartellini: {total_cards_expected:.1f} cards/match (Poisson)"
            ))

        return recommendations

    def _analyze_team_cards(self, home_stats: TeamStats, away_stats: TeamStats) -> List[BettingRecommendation]:
        """Analizza Team Cards (cartellini per squadra) con distribuzione di Poisson."""
        recommendations = []

        for team_stats, label in [(home_stats, "in casa"), (away_stats, "in trasferta")]:
            avg = team_stats.yellow_cards_per_game
            name = team_stats.team.name
            for threshold in [1.5, 2.5]:
                prob = self._poisson_over_prob(avg, threshold) * 100
                if prob >= self.LOW_CONFIDENCE:
                    recommendations.append(self._create_recommendation(
                        market=f"{name} Cards",
                        selection=f"Over {threshold}",
                        probability=prob,
                        reasoning=f"{name}: {avg:.2f} gialli/partita {label} (Poisson)"
                    ))

        return recommendations

