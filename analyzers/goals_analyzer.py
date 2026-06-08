"""
Goals Analyzer - Analisi mercati legati ai gol.

Responsabile di:
- Match Goals (Over/Under totali)
- Team Goals (Over/Under per squadra)
- BTTS (Both Teams To Score)
"""

from typing import List
from .base import BaseAnalyzer
from core.models import TeamStats
from core.betting_models import BettingRecommendation


class GoalsAnalyzer(BaseAnalyzer):
    """Analyzer dedicato ai mercati GOL."""
    
    def get_required_stats(self) -> List[str]:
        """Statistiche necessarie per analisi gol."""
        return [
            'goals_per_game',
            'goals_conceded_per_game',
            'clean_sheets',  # intero, non percentage
            'failed_to_score',  # intero, non percentage
            'matches_played'
        ]
    
    def analyze(self, home_stats: TeamStats, away_stats: TeamStats, **kwargs) -> List[BettingRecommendation]:
        """
        Genera tutte le raccomandazioni legate ai gol.
        
        Returns:
            Lista combinata di Match Goals + Team Goals + BTTS
        """
        if not self._validate_stats(home_stats, away_stats):
            return []
        
        recommendations = []
        
        # 1. Match Goals (totali)
        recommendations.extend(self._analyze_match_goals(home_stats, away_stats))
        
        # 2. Team Goals (per squadra)
        recommendations.extend(self._analyze_team_goals(home_stats, away_stats))
        
        # 3. BTTS
        recommendations.extend(self._analyze_btts(home_stats, away_stats))
        
        return recommendations
    
    def _analyze_match_goals(self, home_stats: TeamStats, away_stats: TeamStats) -> List[BettingRecommendation]:
        """Analizza Match Goals (totali partita) con distribuzione di Poisson."""
        recommendations = []

        total_goals_expected = home_stats.goals_per_game + away_stats.goals_per_game

        # Probabilità Poisson per tutte le soglie
        over_1_5_prob = self._poisson_over_prob(total_goals_expected, 1.5) * 100
        over_2_5_prob = self._poisson_over_prob(total_goals_expected, 2.5) * 100
        over_3_5_prob = self._poisson_over_prob(total_goals_expected, 3.5) * 100
        under_2_5_prob = 100 - over_2_5_prob
        under_3_5_prob = 100 - over_3_5_prob

        candidates = [
            ("Over 3.5", over_3_5_prob, 3),
            ("Over 2.5", over_2_5_prob, 2),
            ("Under 2.5", under_2_5_prob, 1),
            ("Under 3.5", under_3_5_prob, 0.5),
            ("Over 1.5", over_1_5_prob, 0),
        ]

        # Scegli max 2 picks: soglia più alta con prob >= 55%,
        # escludi Over 1.5 se esiste qualcosa di meglio
        has_better = any(prob >= 55 for sel, prob, _ in candidates if sel != "Over 1.5")
        valid = [
            (sel, prob, pri) for sel, prob, pri in candidates
            if prob >= 55 and not (sel == "Over 1.5" and has_better)
        ]
        valid.sort(key=lambda x: (x[2], x[1]), reverse=True)

        for sel, prob, _ in valid[:2]:
            recommendations.append(self._create_recommendation(
                market="Match Goals",
                selection=sel,
                probability=prob,
                reasoning=f"Attesi {total_goals_expected:.1f} gol (Poisson): {prob:.1f}% {sel.lower()}"
            ))

        return recommendations
    
    def _analyze_team_goals(self, home_stats: TeamStats, away_stats: TeamStats) -> List[BettingRecommendation]:
        """Analizza Team Goals (gol singola squadra) con distribuzione di Poisson."""
        recommendations = []

        expected_home = (home_stats.goals_per_game + away_stats.goals_conceded_per_game) / 2
        expected_away = (away_stats.goals_per_game + home_stats.goals_conceded_per_game) / 2

        for team_stats, expected, label in [
            (home_stats, expected_home, "in casa"),
            (away_stats, expected_away, "in trasferta"),
        ]:
            name = team_stats.team.name
            for threshold in [1.5, 2.5]:
                prob = self._poisson_over_prob(expected, threshold) * 100
                if prob >= self.LOW_CONFIDENCE:
                    recommendations.append(self._create_recommendation(
                        market=f"{name} Goals",
                        selection=f"Over {threshold}",
                        probability=prob,
                        reasoning=f"{name} attesi {expected:.1f} gol {label} (Poisson)"
                    ))

        return recommendations
    
    def _analyze_btts(self, home_stats: TeamStats, away_stats: TeamStats) -> List[BettingRecommendation]:
        """Analizza Both Teams To Score."""
        recommendations = []
        
        # Calcola percentuali da attributi interi
        home_scores_prob = 100 - ((home_stats.failed_to_score / home_stats.matches_played) * 100 if home_stats.matches_played > 0 else 50)
        away_scores_prob = 100 - ((away_stats.failed_to_score / away_stats.matches_played) * 100 if away_stats.matches_played > 0 else 50)
        
        # BTTS Yes = entrambe segnano
        btts_yes_prob = (home_scores_prob * away_scores_prob) / 100
        
        # Aggiusta per clean sheets (se squadre subiscono spesso)
        home_concedes_prob = 100 - ((home_stats.clean_sheets / home_stats.matches_played) * 100 if home_stats.matches_played > 0 else 50)
        away_concedes_prob = 100 - ((away_stats.clean_sheets / away_stats.matches_played) * 100 if away_stats.matches_played > 0 else 50)
        btts_adjusted = (btts_yes_prob + ((home_concedes_prob + away_concedes_prob) / 2)) / 2
        
        if btts_adjusted >= self.LOW_CONFIDENCE:
            recommendations.append(self._create_recommendation(
                market="Both Teams to Score",
                selection="Yes",
                probability=btts_adjusted,
                reasoning=f"Entrambe con buon attacco e difese permeabili: {btts_adjusted:.1f}% BTTS"
            ))
        
        # BTTS No
        btts_no_prob = 100 - btts_adjusted
        if btts_no_prob >= self.LOW_CONFIDENCE:
            recommendations.append(self._create_recommendation(
                market="Both Teams to Score",
                selection="No",
                probability=btts_no_prob,
                reasoning=f"Almeno una squadra con difficoltà offensive: {btts_no_prob:.1f}% BTTS No"
            ))
        
        return recommendations

