"""
Result Analyzer - Analisi risultato partita (1X2).

Responsabile di:
- Match Result (1 = Home Win, X = Draw, 2 = Away Win)
"""

from typing import List
from .base import BaseAnalyzer
from core.models import TeamStats
from core.betting_models import BettingRecommendation
from core import shrinkage as sh


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
    
    def result_probabilities(self, home_stats: TeamStats, away_stats: TeamStats) -> dict:
        """
        Probabilità 1X2 normalizzate, come frazioni in [0, 1] che sommano a 1.

        Single source of truth per il mercato risultato: sia analyze() (per le
        raccomandazioni) sia il backtest consumano questo metodo.

        Returns:
            {"1": p_home, "X": p_draw, "2": p_away}
        """
        home_form = self._form_points(home_stats)
        away_form = self._form_points(away_stats)

        # Per-game signals shrunk toward the league average (few games -> prior)
        home_goal_diff = self._goal_diff(home_stats)
        away_goal_diff = self._goal_diff(away_stats)

        # Percentuali vittoria/pareggio/sconfitta storiche (0-100)
        home_win_pct = self._rate(home_stats.wins, home_stats.matches_played, sh.PRIOR_WIN_RATE) * 100
        home_draw_pct = self._rate(home_stats.draws, home_stats.matches_played, sh.PRIOR_DRAW_RATE) * 100
        away_win_pct = self._rate(away_stats.wins, away_stats.matches_played, sh.PRIOR_WIN_RATE) * 100

        # Punteggi grezzi (non ancora probabilità)
        home_raw = (
            40 +  # Base casa
            (home_form - away_form) * 5 +
            home_goal_diff * 10 +
            (home_win_pct - 33) * 0.5
        )
        draw_raw = (
            25
            - abs(home_form - away_form) * 2
            - abs(home_goal_diff - away_goal_diff) * 5
            + home_draw_pct * 0.3
        )
        away_raw = (
            35 +  # Base trasferta (penalità -5 rispetto a casa)
            (away_form - home_form) * 5 +
            away_goal_diff * 10 +
            (away_win_pct - 33) * 0.5
        )

        # Clip negativi prima di normalizzare
        home_raw = max(5.0, home_raw)
        draw_raw = max(5.0, draw_raw)
        away_raw = max(5.0, away_raw)

        # Normalizza (le tre probabilità devono sommare a 1), poi clamp anti-certezza
        total = home_raw + draw_raw + away_raw
        probs = {"1": home_raw / total, "X": draw_raw / total, "2": away_raw / total}
        return self._clamp_and_renormalize(probs)

    @staticmethod
    def _clamp_and_renormalize(probs: dict) -> dict:
        """Clamp each outcome to [P_MIN, P_MAX] and rescale the rest so the sum stays 1."""
        clamped = {k: sh.clamp_probability(v) for k, v in probs.items()}
        total = sum(clamped.values())
        return {k: v / total for k, v in clamped.items()}

    @staticmethod
    def _rate(successes: int, games: int, prior: float) -> float:
        return sh.shrink(successes, games, prior, sh.K_RESULT)

    @staticmethod
    def _goal_diff(stats: TeamStats) -> float:
        """Goal difference per game shrunk toward 0."""
        return sh.shrink(stats.goals_for - stats.goals_against, stats.matches_played,
                         sh.PRIOR_GOAL_DIFF_PER_GAME, sh.K_RESULT)

    @staticmethod
    def _form_points(stats: TeamStats) -> float:
        """Points over the last (up to) 5 games, on a 5-game scale, shrunk toward league PPG."""
        form = stats.form[-5:] if stats.form else ""
        pts = stats.recent_form_points
        return 5 * sh.shrink(pts, len(form), sh.PRIOR_POINTS_PER_GAME, sh.K_RESULT)

    def analyze(self, home_stats: TeamStats, away_stats: TeamStats, **kwargs) -> List[BettingRecommendation]:
        """
        Genera raccomandazione per il risultato finale (1X2).

        Restituisce SOLO il risultato più probabile, non tutti e 3.

        Returns:
            Lista con UN SOLO pronostico (il più probabile)
        """
        if not self._validate_stats(home_stats, away_stats):
            return []

        probs = self.result_probabilities(home_stats, away_stats)
        home_win_prob = round(probs["1"] * 100, 1)
        draw_prob = round(probs["X"] * 100, 1)
        away_win_prob = round(probs["2"] * 100, 1)

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

