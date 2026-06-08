"""
Betting Orchestrator — coordinates all market analyzers.

Uses the ANALYZER_REGISTRY as its plugin list.  To enable or disable a
market, edit the registry in analyzers/__init__.py — no changes needed here.

To run with a custom subset at call time:
    orchestrator = BettingOrchestrator(enabled={"goals": GoalsAnalyzer})
"""

from typing import Dict, List, Optional, Type

from core.models import TeamStats
from core.betting_models import BettingRecommendation, MatchBettingAnalysis, ExactScorePrediction

from analyzers import ANALYZER_REGISTRY
from analyzers.base import BaseAnalyzer
from analyzers.score_analyzer import ScoreAnalyzer


class BettingOrchestrator:
    """
    Coordinates all registered market analyzers and aggregates results.

    Lifecycle: instantiate once, call analyze_match() for each fixture.
    Stateless across calls — safe to reuse.
    """

    def __init__(self, enabled: Optional[Dict[str, Optional[Type[BaseAnalyzer]]]] = None):
        """
        Args:
            enabled: Override the default ANALYZER_REGISTRY.
                     Pass None to use all registered analyzers.
                     Pass a subset dict to enable only specific markets.
                     Setting a value to None disables that key.
        """
        registry = enabled if enabled is not None else ANALYZER_REGISTRY
        self._analyzers: Dict[str, BaseAnalyzer] = {
            name: cls()
            for name, cls in registry.items()
            if cls is not None
        }
        self._score_analyzer = ScoreAnalyzer()

    # ── public ────────────────────────────────────────────────────────────────

    def analyze_match(
        self,
        home_stats: TeamStats,
        away_stats: TeamStats,
        home_position: int = None,
        away_position: int = None,
    ) -> MatchBettingAnalysis:
        """Run all active analyzers and return a combined betting analysis."""
        all_recommendations: List[BettingRecommendation] = []

        for name, analyzer in self._analyzers.items():
            try:
                recs = analyzer.analyze(
                    home_stats, away_stats,
                    home_position=home_position,
                    away_position=away_position,
                )
                all_recommendations.extend(recs)
            except Exception as exc:
                print(f"⚠️ Analyzer '{name}' failed: {exc}")

        # ScoreAnalyzer runs separately — it needs the predicted result from ResultAnalyzer
        predicted_result = self._infer_result(all_recommendations)
        exact_scores = self._score_analyzer.predict_exact_scores(
            home_stats, away_stats, top_n=3, predicted_result=predicted_result
        )

        return MatchBettingAnalysis(
            match_info=f"{home_stats.team.name} vs {away_stats.team.name}",
            recommendations=all_recommendations,
            exact_scores=exact_scores,
            summary=self._generate_summary(all_recommendations, exact_scores),
            player_predictions=None,
        )

    def active_analyzers(self) -> List[str]:
        """Return names of currently active analyzers (for display/logging)."""
        return list(self._analyzers.keys())

    def get_required_stats_all(self) -> Dict[str, List[str]]:
        """Return {analyzer_name: [required_stat_names]} for all active analyzers."""
        return {name: az.get_required_stats() for name, az in self._analyzers.items()}

    # ── private ───────────────────────────────────────────────────────────────

    @staticmethod
    def _infer_result(recs: List[BettingRecommendation]) -> Optional[str]:
        """Derive predicted match result ('1'/'X'/'2') from ResultAnalyzer output."""
        for rec in recs:
            if rec.market == "Match Result":
                sel = rec.selection
                if "Home Win" in sel or sel.startswith("1"):
                    return "1"
                if "Draw" in sel or sel.startswith("X"):
                    return "X"
                if "Away Win" in sel or sel.startswith("2"):
                    return "2"
        return None

    @staticmethod
    def _generate_summary(
        recs: List[BettingRecommendation],
        exact_scores: List[ExactScorePrediction],
    ) -> Dict:
        high = sum(1 for r in recs if r.confidence == "HIGH")
        medium = sum(1 for r in recs if r.confidence == "MEDIUM")
        low = sum(1 for r in recs if r.confidence == "LOW")

        top_pick = top_market = None
        if recs:
            best = max(recs, key=lambda r: r.percentage)
            top_pick = f"{best.market}: {best.selection}"
            top_market = best.market

        return {
            "total_recommendations": len(recs),
            "high_confidence": high,
            "medium_confidence": medium,
            "low_confidence": low,
            "top_pick": top_pick or "None",
            "top_market": top_market or "None",
            "most_likely_score": exact_scores[0].score if exact_scores else "N/A",
        }
