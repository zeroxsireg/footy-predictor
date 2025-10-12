"""
Shots Analyzer - Analisi mercati legati ai tiri.

Responsabile di:
- Total Shots (tiri totali)
- Shots on Goal / Shots on Target (tiri in porta)
- Team Shots (tiri per squadra)
"""

from typing import List
from .base import BaseAnalyzer
from core.models import TeamStats
from core.betting_models import BettingRecommendation


class ShotsAnalyzer(BaseAnalyzer):
    """Analyzer dedicato ai mercati TIRI."""
    
    def get_required_stats(self) -> List[str]:
        """Statistiche necessarie per analisi tiri."""
        return [
            'shots_per_game',
            'shots_on_target_per_game'
        ]
    
    def analyze(self, home_stats: TeamStats, away_stats: TeamStats, **kwargs) -> List[BettingRecommendation]:
        """
        Genera tutte le raccomandazioni legate ai tiri.
        
        Returns:
            Lista combinata di Total Shots + Shots on Goal + Team Shots
        """
        if not self._validate_stats(home_stats, away_stats):
            return []
        
        recommendations = []
        
        # 1. Total Shots
        recommendations.extend(self._analyze_total_shots(home_stats, away_stats))
        
        # 2. Shots on Goal (totali)
        recommendations.extend(self._analyze_shots_on_goal(home_stats, away_stats))
        
        # 3. Team Shots (tiri per squadra)
        recommendations.extend(self._analyze_team_shots(home_stats, away_stats))
        
        # 4. Team Shots on Goal (tiri in porta per squadra)
        recommendations.extend(self._analyze_team_shots_on_goal(home_stats, away_stats))
        
        return recommendations
    
    def _analyze_total_shots(self, home_stats: TeamStats, away_stats: TeamStats) -> List[BettingRecommendation]:
        """Analizza Total Shots (tiri totali)."""
        recommendations = []
        
        home_shots_avg = home_stats.shots_per_game
        away_shots_avg = away_stats.shots_per_game
        total_shots_expected = home_shots_avg + away_shots_avg
        
        # Soglie disponibili
        thresholds = [
            (16.5, "1.20-1.50"),
            (18.5, "1.30-1.60"),
            (20.5, "1.40-1.80"),
            (24.5, "1.70-2.20"),
            (28.5, "2.20-3.00")
        ]
        
        # STRATEGIA OTTIMALE: Seleziona la soglia PIÙ ALTA che abbia ancora prob >= 60%
        # Es: 15.7 shots attesi → Over 16.5 NO (troppo alto), Over 18.5 NO, prova più basse
        # Ma se 23 shots → Over 20.5 o Over 18.5 (sceglie la più alta)
        best_threshold = None
        best_prob = 0
        
        for threshold, _ in thresholds:
            # Calcola probabilità per questa soglia
            if total_shots_expected >= threshold:
                prob = min(95, 50 + (total_shots_expected - threshold) * 10)
            else:
                prob = max(5, (total_shots_expected / threshold) * 50)
            
            # Cerca la soglia PIÙ ALTA con prob >= 60% (sweet spot)
            if prob >= 60:
                if threshold > (best_threshold or 0):  # Prendi la più alta
                    best_threshold = threshold
                    best_prob = prob
        
        # Genera raccomandazione
        if best_threshold and best_prob >= self.LOW_CONFIDENCE:
            recommendations.append(self._create_recommendation(
                market="Total Shots",
                selection=f"Over {best_threshold}",
                probability=best_prob,
                odds_range=None,  # Quote rimosse
                reasoning=f"Volume tiri: {total_shots_expected:.1f} shots/match"
            ))
        
        return recommendations
    
    def _analyze_shots_on_goal(self, home_stats: TeamStats, away_stats: TeamStats) -> List[BettingRecommendation]:
        """Analizza Shots on Goal (tiri in porta)."""
        recommendations = []
        
        home_sog_avg = home_stats.shots_on_target_per_game
        away_sog_avg = away_stats.shots_on_target_per_game
        total_sog_expected = home_sog_avg + away_sog_avg
        
        # Soglie disponibili
        thresholds = [
            (4.5, "1.20-1.50"),
            (6.5, "1.40-1.70"),
            (8.5, "1.60-2.00"),
            (10.5, "2.00-2.60")
        ]
        
        # STRATEGIA OTTIMALE: Seleziona la soglia PIÙ ALTA con prob >= 60%
        best_threshold = None
        best_prob = 0
        
        for threshold, _ in thresholds:
            # Calcola probabilità per questa soglia
            if total_sog_expected >= threshold:
                prob = min(95, 50 + (total_sog_expected - threshold) * 15)
            else:
                prob = max(5, (total_sog_expected / threshold) * 50)
            
            # Cerca la soglia PIÙ ALTA con prob >= 60%
            if prob >= 60:
                if threshold > (best_threshold or 0):
                    best_threshold = threshold
                    best_prob = prob
        
        if best_threshold and best_prob >= self.LOW_CONFIDENCE:
            recommendations.append(self._create_recommendation(
                market="Total Shots on Goal",
                selection=f"Over {best_threshold}",
                probability=best_prob,
                odds_range=None,  # Quote rimosse
                reasoning=f"Precisione tiri: {total_sog_expected:.1f} shots on goal/match"
            ))
        
        return recommendations
    
    def _analyze_team_shots(self, home_stats: TeamStats, away_stats: TeamStats) -> List[BettingRecommendation]:
        """Analizza Team Shots (tiri per squadra)."""
        recommendations = []
        
        home_shots_avg = home_stats.shots_per_game
        away_shots_avg = away_stats.shots_per_game
        
        # Home Team Shots (soglie più basse per includere entrambe le squadre)
        home_thresholds = [8.5, 10.5, 12.5, 14.5]
        best_home_threshold = None
        best_home_prob = 0
        
        for threshold in home_thresholds:
            if home_shots_avg >= threshold:
                prob = min(90, 50 + (home_shots_avg - threshold) * 10)
            else:
                prob = max(10, (home_shots_avg / threshold) * 50)
            
            if prob >= 60 and threshold > (best_home_threshold or 0):
                best_home_threshold = threshold
                best_home_prob = prob
        
        if best_home_threshold and best_home_prob >= self.LOW_CONFIDENCE:
            recommendations.append(self._create_recommendation(
                market=f"{home_stats.team.name} Shots",
                selection=f"Over {best_home_threshold}",
                probability=best_home_prob,
                reasoning=f"{home_stats.team.name}: {home_shots_avg:.1f} shots/match"
            ))
        
        # Away Team Shots - Seleziona la soglia PIÙ ALTA con prob >= 60%
        away_thresholds = [8.5, 10.5, 12.5, 14.5]
        best_away_threshold = None
        best_away_prob = 0
        
        for threshold in away_thresholds:
            if away_shots_avg >= threshold:
                prob = min(90, 50 + (away_shots_avg - threshold) * 10)
            else:
                prob = max(10, (away_shots_avg / threshold) * 50)
            
            if prob >= 60 and threshold > (best_away_threshold or 0):
                best_away_threshold = threshold
                best_away_prob = prob
        
        if best_away_threshold and best_away_prob >= self.LOW_CONFIDENCE:
            recommendations.append(self._create_recommendation(
                market=f"{away_stats.team.name} Shots",
                selection=f"Over {best_away_threshold}",
                probability=best_away_prob,
                reasoning=f"{away_stats.team.name}: {away_shots_avg:.1f} shots/match"
            ))
        
        return recommendations
    
    def _analyze_team_shots_on_goal(self, home_stats: TeamStats, away_stats: TeamStats) -> List[BettingRecommendation]:
        """Analizza Team Shots on Goal (tiri in porta per squadra)."""
        recommendations = []
        
        home_sog_avg = home_stats.shots_on_target_per_game
        away_sog_avg = away_stats.shots_on_target_per_game
        
        # Home Team Shots on Goal - Seleziona la soglia PIÙ ALTA con prob >= 60%
        home_thresholds = [2.5, 3.5, 4.5, 5.5]
        best_home_threshold = None
        best_home_prob = 0
        
        for threshold in home_thresholds:
            if home_sog_avg >= threshold:
                prob = min(90, 50 + (home_sog_avg - threshold) * 15)
            else:
                prob = max(10, (home_sog_avg / threshold) * 50)
            
            if prob >= 60 and threshold > (best_home_threshold or 0):
                best_home_threshold = threshold
                best_home_prob = prob
        
        if best_home_threshold and best_home_prob >= self.LOW_CONFIDENCE:
            recommendations.append(self._create_recommendation(
                market=f"{home_stats.team.name} Shots on Goal",
                selection=f"Over {best_home_threshold}",
                probability=best_home_prob,
                reasoning=f"{home_stats.team.name}: {home_sog_avg:.1f} shots on goal/match"
            ))
        
        # Away Team Shots on Goal - Seleziona la soglia PIÙ ALTA con prob >= 60%
        away_thresholds = [2.5, 3.5, 4.5, 5.5]
        best_away_threshold = None
        best_away_prob = 0
        
        for threshold in away_thresholds:
            if away_sog_avg >= threshold:
                prob = min(90, 50 + (away_sog_avg - threshold) * 15)
            else:
                prob = max(10, (away_sog_avg / threshold) * 50)
            
            if prob >= 60 and threshold > (best_away_threshold or 0):
                best_away_threshold = threshold
                best_away_prob = prob
        
        if best_away_threshold and best_away_prob >= self.LOW_CONFIDENCE:
            recommendations.append(self._create_recommendation(
                market=f"{away_stats.team.name} Shots on Goal",
                selection=f"Over {best_away_threshold}",
                probability=best_away_prob,
                reasoning=f"{away_stats.team.name}: {away_sog_avg:.1f} shots on goal/match"
            ))
        
        return recommendations

