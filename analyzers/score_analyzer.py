"""
Score Analyzer - Analisi punteggio esatto.

Responsabile di:
- Exact Score predictions (punteggi più probabili)
"""

from typing import List
from .base import BaseAnalyzer
from core.models import TeamStats
from core.betting_models import BettingRecommendation, ExactScorePrediction


class ScoreAnalyzer(BaseAnalyzer):
    """Analyzer dedicato ai PUNTEGGI ESATTI."""
    
    def get_required_stats(self) -> List[str]:
        """Statistiche necessarie per analisi punteggio."""
        return [
            'goals_per_game',
            'goals_conceded_per_game'
        ]
    
    def analyze(self, home_stats: TeamStats, away_stats: TeamStats, **kwargs) -> List[BettingRecommendation]:
        """
        Questo analyzer non genera BettingRecommendation ma ExactScorePrediction.
        Implementato per compatibilità con BaseAnalyzer.
        
        Usa invece predict_exact_scores().
        """
        return []
    
    def predict_exact_scores(self, home_stats: TeamStats, away_stats: TeamStats, 
                            top_n: int = 3, predicted_result: str = None) -> List[ExactScorePrediction]:
        """
        Predice i punteggi esatti più probabili.
        
        Args:
            home_stats: Statistiche squadra casa
            away_stats: Statistiche squadra trasferta
            top_n: Numero di punteggi da ritornare (default 3)
            predicted_result: Risultato previsto ("1", "X", "2") per filtrare scores coerenti
            
        Returns:
            List[ExactScorePrediction]: Top N punteggi più probabili coerenti con il risultato previsto
        """
        if not self._validate_stats(home_stats, away_stats):
            return []
        
        # Calcola gol attesi per squadra
        home_goals_avg = home_stats.goals_per_game
        away_goals_avg = away_stats.goals_per_game
        home_conceded_avg = home_stats.goals_conceded_per_game
        away_conceded_avg = away_stats.goals_conceded_per_game
        
        expected_home_goals = (home_goals_avg + away_conceded_avg) / 2
        expected_away_goals = (away_goals_avg + home_conceded_avg) / 2
        
        # Genera possibili punteggi (0-0 fino a 4-4)
        score_predictions = []
        
        for home_goals in range(5):
            for away_goals in range(5):
                # Calcola probabilità usando distribuzione di Poisson semplificata
                prob = self._calculate_score_probability(
                    home_goals, away_goals,
                    expected_home_goals, expected_away_goals
                )
                
                # Determina emoji risultato
                if home_goals > away_goals:
                    result_emoji = "🏠"  # Home win
                elif home_goals < away_goals:
                    result_emoji = "✈️"  # Away win
                else:
                    result_emoji = "🤝"  # Draw
                
                score_predictions.append(ExactScorePrediction(
                    score=f"{home_goals}-{away_goals}",
                    probability=prob,
                    odds_estimate="8.00-15.00" if prob < 15 else "6.00-10.00" if prob < 20 else "4.00-8.00",
                    reasoning=f"Based on {expected_home_goals:.1f} vs {expected_away_goals:.1f} expected goals"
                ))
        
        # Filtra per risultato previsto (se specificato)
        if predicted_result:
            filtered_predictions = []
            for pred in score_predictions:
                home_g, away_g = map(int, pred.score.split('-'))
                
                if predicted_result == "1" and home_g > away_g:  # Home Win
                    filtered_predictions.append(pred)
                elif predicted_result == "X" and home_g == away_g:  # Draw
                    filtered_predictions.append(pred)
                elif predicted_result == "2" and home_g < away_g:  # Away Win
                    filtered_predictions.append(pred)
            
            score_predictions = filtered_predictions
        
        # Ordina per probabilità e ritorna top N
        score_predictions.sort(key=lambda x: x.probability, reverse=True)
        return score_predictions[:top_n]
    
    def _calculate_score_probability(self, home_goals: int, away_goals: int,
                                    expected_home: float, expected_away: float) -> float:
        """
        Calcola probabilità di un punteggio specifico.
        
        Usa distribuzione di Poisson semplificata.
        """
        import math
        
        # Poisson probability mass function
        def poisson_pmf(k: int, lambda_val: float) -> float:
            if lambda_val == 0:
                return 1.0 if k == 0 else 0.0
            return (lambda_val ** k * math.exp(-lambda_val)) / math.factorial(k)
        
        # Probabilità indipendenti per casa e trasferta
        home_prob = poisson_pmf(home_goals, expected_home)
        away_prob = poisson_pmf(away_goals, expected_away)
        
        # Probabilità combinata
        combined_prob = home_prob * away_prob * 100  # In percentuale
        
        return round(combined_prob, 2)

