"""Core modules for the footy predictor application."""

from .models import Team, Fixture, TeamStats, MatchPrediction
from .config import get_settings
from .analyzer import MatchAnalyzer
from .betting_predictions import BettingPredictor, BettingRecommendation, MatchBettingAnalysis, ExactScorePrediction

__all__ = [
    "Team", "Fixture", "TeamStats", "MatchPrediction",
    "get_settings", "MatchAnalyzer",
    "BettingPredictor", "BettingRecommendation", "MatchBettingAnalysis", "ExactScorePrediction"
]