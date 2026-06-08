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
        return ['shots_per_game', 'shots_on_target_per_game']

    def analyze(self, home_stats: TeamStats, away_stats: TeamStats, **kwargs) -> List[BettingRecommendation]:
        if not self._validate_stats(home_stats, away_stats):
            return []

        recommendations = []
        recommendations.extend(self._analyze_total_shots(home_stats, away_stats))
        recommendations.extend(self._analyze_shots_on_goal(home_stats, away_stats))
        recommendations.extend(self._analyze_team_shots(home_stats, away_stats))
        recommendations.extend(self._analyze_team_shots_on_goal(home_stats, away_stats))
        return recommendations

    # ── helper interno ────────────────────────────────────────────────────────

    def _best_over_threshold(self, lambda_val: float, thresholds: list) -> tuple:
        """Restituisce (best_threshold, best_prob) con Poisson, min prob 60%."""
        best_threshold = None
        best_prob = 0.0
        for threshold in thresholds:
            prob = self._poisson_over_prob(lambda_val, threshold) * 100
            if prob >= 60.0 and threshold > (best_threshold or 0):
                best_threshold = threshold
                best_prob = prob
        return best_threshold, best_prob

    # ── analisi totali ────────────────────────────────────────────────────────

    def _analyze_total_shots(self, home_stats: TeamStats, away_stats: TeamStats) -> List[BettingRecommendation]:
        """Analizza Total Shots con distribuzione di Poisson."""
        total = home_stats.shots_per_game + away_stats.shots_per_game
        if total == 0:
            return []

        best_thr, best_prob = self._best_over_threshold(total, [16.5, 18.5, 20.5, 24.5, 28.5])
        if best_thr and best_prob >= self.LOW_CONFIDENCE:
            return [self._create_recommendation(
                market="Total Shots",
                selection=f"Over {best_thr}",
                probability=best_prob,
                reasoning=f"Volume tiri: {total:.1f} shots/match (Poisson)"
            )]
        return []

    def _analyze_shots_on_goal(self, home_stats: TeamStats, away_stats: TeamStats) -> List[BettingRecommendation]:
        """Analizza Total Shots on Goal con distribuzione di Poisson."""
        total = home_stats.shots_on_target_per_game + away_stats.shots_on_target_per_game
        if total == 0:
            return []

        best_thr, best_prob = self._best_over_threshold(total, [4.5, 6.5, 8.5, 10.5])
        if best_thr and best_prob >= self.LOW_CONFIDENCE:
            return [self._create_recommendation(
                market="Total Shots on Goal",
                selection=f"Over {best_thr}",
                probability=best_prob,
                reasoning=f"Precisione tiri: {total:.1f} shots on goal/match (Poisson)"
            )]
        return []

    # ── analisi per squadra ───────────────────────────────────────────────────

    def _analyze_team_shots(self, home_stats: TeamStats, away_stats: TeamStats) -> List[BettingRecommendation]:
        """Analizza Team Shots (tiri per squadra) con distribuzione di Poisson."""
        recommendations = []
        for team_stats, label in [(home_stats, "in casa"), (away_stats, "in trasferta")]:
            avg = team_stats.shots_per_game
            if avg == 0:
                continue
            best_thr, best_prob = self._best_over_threshold(avg, [8.5, 10.5, 12.5, 14.5])
            if best_thr and best_prob >= self.LOW_CONFIDENCE:
                recommendations.append(self._create_recommendation(
                    market=f"{team_stats.team.name} Shots",
                    selection=f"Over {best_thr}",
                    probability=best_prob,
                    reasoning=f"{team_stats.team.name}: {avg:.1f} shots/match {label} (Poisson)"
                ))
        return recommendations

    def _analyze_team_shots_on_goal(self, home_stats: TeamStats, away_stats: TeamStats) -> List[BettingRecommendation]:
        """Analizza Team Shots on Goal (tiri in porta per squadra) con distribuzione di Poisson."""
        recommendations = []
        for team_stats, label in [(home_stats, "in casa"), (away_stats, "in trasferta")]:
            avg = team_stats.shots_on_target_per_game
            if avg == 0:
                continue
            best_thr, best_prob = self._best_over_threshold(avg, [2.5, 3.5, 4.5, 5.5])
            if best_thr and best_prob >= self.LOW_CONFIDENCE:
                recommendations.append(self._create_recommendation(
                    market=f"{team_stats.team.name} Shots on Goal",
                    selection=f"Over {best_thr}",
                    probability=best_prob,
                    reasoning=f"{team_stats.team.name}: {avg:.1f} shots on goal/match {label} (Poisson)"
                ))
        return recommendations
