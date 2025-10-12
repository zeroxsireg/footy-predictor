"""
Betting Orchestrator - Coordina tutti gli analyzer di mercato.

Responsabile di:
- Inizializzare tutti gli analyzer
- Coordinare l'analisi
- Aggregare le raccomandazioni
- Generare summary
"""

from typing import List, Dict
from core.models import TeamStats
from core.betting_models import BettingRecommendation, MatchBettingAnalysis, ExactScorePrediction

from analyzers.goals_analyzer import GoalsAnalyzer
from analyzers.shots_analyzer import ShotsAnalyzer
from analyzers.corners_analyzer import CornersAnalyzer
from analyzers.cards_analyzer import CardsAnalyzer
from analyzers.result_analyzer import ResultAnalyzer
from analyzers.score_analyzer import ScoreAnalyzer
from analyzers.player_cards_analyzer import PlayerCardsAnalyzer


class BettingOrchestrator:
    """
    Orchestrator centrale per analisi betting.
    
    Coordina tutti i moduli analyzer e genera analisi completa.
    Ogni analyzer è responsabile solo del suo mercato specifico.
    """
    
    def __init__(self):
        """Inizializza tutti gli analyzer."""
        self.goals_analyzer = GoalsAnalyzer()
        self.shots_analyzer = ShotsAnalyzer()
        self.corners_analyzer = CornersAnalyzer()
        self.cards_analyzer = CardsAnalyzer()
        self.result_analyzer = ResultAnalyzer()
        self.score_analyzer = ScoreAnalyzer()
        self.player_cards_analyzer = PlayerCardsAnalyzer()  # Disabilitato by default
    
    def analyze_match(self, home_stats: TeamStats, away_stats: TeamStats,
                     home_position: int = None, away_position: int = None) -> MatchBettingAnalysis:
        """
        Genera analisi betting completa per una partita.
        
        Args:
            home_stats: Statistiche squadra casa
            away_stats: Statistiche squadra trasferta
            home_position: Posizione in classifica casa (opzionale)
            away_position: Posizione in classifica trasferta (opzionale)
            
        Returns:
            MatchBettingAnalysis: Analisi completa con tutte le raccomandazioni
        """
        all_recommendations = []
        
        # Esegui analisi modulo per modulo (silent mode)
        all_recommendations.extend(
            self.goals_analyzer.analyze(home_stats, away_stats)
        )
        
        all_recommendations.extend(
            self.shots_analyzer.analyze(home_stats, away_stats)
        )
        
        all_recommendations.extend(
            self.corners_analyzer.analyze(home_stats, away_stats)
        )
        
        all_recommendations.extend(
            self.cards_analyzer.analyze(home_stats, away_stats,
                                       home_position=home_position,
                                       away_position=away_position)
        )
        
        result_recs = self.result_analyzer.analyze(home_stats, away_stats)
        all_recommendations.extend(result_recs)
        
        # Estrai il risultato previsto per filtrare gli exact scores
        predicted_result = None
        if result_recs:
            # Il result_analyzer restituisce solo 1 raccomandazione (la più probabile)
            selection = result_recs[0].selection
            if "Home Win" in selection or selection.startswith("1"):
                predicted_result = "1"
            elif "Draw" in selection or selection.startswith("X"):
                predicted_result = "X"
            elif "Away Win" in selection or selection.startswith("2"):
                predicted_result = "2"
        
        exact_scores = self.score_analyzer.predict_exact_scores(
            home_stats, away_stats, top_n=3, predicted_result=predicted_result
        )
        
        # Genera summary
        summary = self._generate_summary(all_recommendations, exact_scores)
        
        # Match info string
        match_info = f"{home_stats.team.name} vs {away_stats.team.name}"
        
        return MatchBettingAnalysis(
            match_info=match_info,
            recommendations=all_recommendations,
            exact_scores=exact_scores,
            summary=summary,
            player_predictions=None  # Player cards per dopo
        )
    
    def _generate_summary(self, recommendations: List[BettingRecommendation],
                         exact_scores: List[ExactScorePrediction]) -> Dict:
        """Genera summary dell'analisi."""
        high_conf = len([r for r in recommendations if r.confidence == "HIGH"])
        medium_conf = len([r for r in recommendations if r.confidence == "MEDIUM"])
        low_conf = len([r for r in recommendations if r.confidence == "LOW"])
        
        # Top pick = raccomandazione con probability più alta
        top_pick = None
        top_market = None
        if recommendations:
            sorted_recs = sorted(recommendations, key=lambda x: x.percentage, reverse=True)
            top_pick = f"{sorted_recs[0].market}: {sorted_recs[0].selection}"
            top_market = sorted_recs[0].market
        
        # Most likely score
        most_likely_score = None
        if exact_scores:
            most_likely_score = exact_scores[0].score
        
        return {
            'total_recommendations': len(recommendations),
            'high_confidence': high_conf,
            'medium_confidence': medium_conf,
            'low_confidence': low_conf,
            'top_pick': top_pick or "None",
            'top_market': top_market or "None",
            'most_likely_score': most_likely_score or "N/A"
        }
    
    def get_required_stats_all(self) -> Dict[str, List[str]]:
        """
        Ritorna tutte le statistiche necessarie per tutti i moduli.
        
        Returns:
            Dict con analyzer_name -> lista stats necessarie
        """
        return {
            'goals': self.goals_analyzer.get_required_stats(),
            'shots': self.shots_analyzer.get_required_stats(),
            'corners': self.corners_analyzer.get_required_stats(),
            'cards': self.cards_analyzer.get_required_stats(),
            'result': self.result_analyzer.get_required_stats(),
            'score': self.score_analyzer.get_required_stats()
        }

