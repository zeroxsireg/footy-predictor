"""
Corners Analyzer - Analisi mercati legati ai corner.

Responsabile di:
- Total Corners (corner totali)
- Team Corners (corner per squadra)
"""

from typing import List
from .base import BaseAnalyzer
from core.models import TeamStats
from core.betting_models import BettingRecommendation


class CornersAnalyzer(BaseAnalyzer):
    """Analyzer dedicato ai mercati CORNER."""
    
    def get_required_stats(self) -> List[str]:
        """Statistiche necessarie per analisi corner."""
        return ['corners_per_game']
    
    def analyze(self, home_stats: TeamStats, away_stats: TeamStats, **kwargs) -> List[BettingRecommendation]:
        """
        Genera tutte le raccomandazioni legate ai corner.
        
        Returns:
            Lista combinata di Total Corners + Team Corners
        """
        if not self._validate_stats(home_stats, away_stats):
            return []
        
        recommendations = []
        
        # 1. Total Corners
        recommendations.extend(self._analyze_total_corners(home_stats, away_stats))
        
        # 2. Team Corners
        recommendations.extend(self._analyze_team_corners(home_stats, away_stats))
        
        return recommendations
    
    def _analyze_total_corners(self, home_stats: TeamStats, away_stats: TeamStats) -> List[BettingRecommendation]:
        """Analizza Total Corners (corner totali) con distribuzione di Poisson."""
        recommendations = []

        total_corners_expected = home_stats.corners_per_game + away_stats.corners_per_game

        if total_corners_expected == 0:
            return recommendations

        best_threshold = None
        best_prob = 0.0
        for threshold in [6.5, 8.5, 10.5, 12.5, 14.5]:
            prob = self._poisson_over_prob(total_corners_expected, threshold) * 100
            if prob >= 60.0 and threshold > (best_threshold or 0):
                best_threshold = threshold
                best_prob = prob

        if best_threshold and best_prob >= self.LOW_CONFIDENCE:
            level = "Alto" if best_threshold >= 12 else "Medio" if best_threshold >= 10 else "Normale"
            recommendations.append(self._create_recommendation(
                market="Total Corners",
                selection=f"Over {best_threshold}",
                probability=best_prob,
                reasoning=f"{level} volume corner: {total_corners_expected:.1f} corners/match (Poisson)"
            ))

        return recommendations

    def _analyze_team_corners(self, home_stats: TeamStats, away_stats: TeamStats) -> List[BettingRecommendation]:
        """Analizza Team Corners (corner per squadra) con distribuzione di Poisson."""
        recommendations = []

        for team_stats, label in [(home_stats, "in casa"), (away_stats, "in trasferta")]:
            avg = team_stats.corners_per_game
            if avg == 0:
                continue
            name = team_stats.team.name
            best_threshold = None
            best_prob = 0.0
            for threshold in [3.5, 4.5, 5.5, 6.5]:
                prob = self._poisson_over_prob(avg, threshold) * 100
                if prob >= 60.0 and threshold > (best_threshold or 0):
                    best_threshold = threshold
                    best_prob = prob

            if best_threshold and best_prob >= self.LOW_CONFIDENCE:
                recommendations.append(self._create_recommendation(
                    market=f"{name} Corners",
                    selection=f"Over {best_threshold}",
                    probability=best_prob,
                    reasoning=f"{name}: {avg:.1f} corners/match {label} (Poisson)"
                ))

        return recommendations

