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
        """Analizza Total Corners (corner totali)."""
        recommendations = []
        
        home_corners_avg = home_stats.corners_per_game
        away_corners_avg = away_stats.corners_per_game
        total_corners_expected = home_corners_avg + away_corners_avg
        
        # Soglie da rivedere (come richiesto)
        thresholds = [
            (6.5, "1.20-1.50"),   # Molto basso
            (8.5, "1.30-1.70"),   # Basso
            (10.5, "1.60-2.20"),  # Medio
            (12.5, "2.00-2.80"),  # Alto
            (14.5, "2.50-3.50")   # Molto alto
        ]
        
        # STRATEGIA OTTIMALE: Seleziona la soglia PIÙ ALTA con prob >= 60%
        best_threshold = None
        best_prob = 0
        
        for threshold, _ in thresholds:
            # Calcola probabilità per questa soglia
            if total_corners_expected >= threshold:
                prob = min(95, 50 + (total_corners_expected - threshold) * 15)
            else:
                prob = max(5, (total_corners_expected / threshold) * 50)
            
            # Cerca la soglia PIÙ ALTA con prob >= 60%
            if prob >= 60:
                if threshold > (best_threshold or 0):
                    best_threshold = threshold
                    best_prob = prob
        
        if best_threshold and best_prob >= self.LOW_CONFIDENCE:
            level = "Alto" if best_threshold >= 12 else "Medio" if best_threshold >= 10 else "Normale"
            recommendations.append(self._create_recommendation(
                market="Total Corners",
                selection=f"Over {best_threshold}",
                probability=best_prob,
                odds_range=None,  # Quote rimosse
                reasoning=f"{level} volume corner: {total_corners_expected:.1f} corners/match"
            ))
        
        return recommendations
    
    def _analyze_team_corners(self, home_stats: TeamStats, away_stats: TeamStats) -> List[BettingRecommendation]:
        """Analizza Team Corners (corner per squadra)."""
        recommendations = []
        
        home_corners_avg = home_stats.corners_per_game
        away_corners_avg = away_stats.corners_per_game
        
        # Home Team Corners - Seleziona la soglia PIÙ ALTA con prob >= 60%
        home_thresholds = [3.5, 4.5, 5.5, 6.5]
        best_home_threshold = None
        best_home_prob = 0
        
        for threshold in home_thresholds:
            if home_corners_avg >= threshold:
                prob = min(90, 50 + (home_corners_avg - threshold) * 15)
            else:
                prob = max(10, (home_corners_avg / threshold) * 50)
            
            if prob >= 60 and threshold > (best_home_threshold or 0):
                best_home_threshold = threshold
                best_home_prob = prob
        
        if best_home_threshold and best_home_prob >= self.LOW_CONFIDENCE:
            recommendations.append(self._create_recommendation(
                market=f"{home_stats.team.name} Corners",
                selection=f"Over {best_home_threshold}",
                probability=best_home_prob,
                reasoning=f"{home_stats.team.name}: {home_corners_avg:.1f} corners/match"
            ))
        
        # Away Team Corners - Seleziona la soglia PIÙ ALTA con prob >= 60%
        away_thresholds = [3.5, 4.5, 5.5, 6.5]
        best_away_threshold = None
        best_away_prob = 0
        
        for threshold in away_thresholds:
            if away_corners_avg >= threshold:
                prob = min(90, 50 + (away_corners_avg - threshold) * 15)
            else:
                prob = max(10, (away_corners_avg / threshold) * 50)
            
            if prob >= 60 and threshold > (best_away_threshold or 0):
                best_away_threshold = threshold
                best_away_prob = prob
        
        if best_away_threshold and best_away_prob >= self.LOW_CONFIDENCE:
            recommendations.append(self._create_recommendation(
                market=f"{away_stats.team.name} Corners",
                selection=f"Over {best_away_threshold}",
                probability=best_away_prob,
                reasoning=f"{away_stats.team.name}: {away_corners_avg:.1f} corners/match in trasferta"
            ))
        
        return recommendations

