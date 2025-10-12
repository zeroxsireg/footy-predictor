"""Betting prediction models and data structures."""

from dataclasses import dataclass
from typing import List, Dict, Optional
from .player_predictions import MatchPlayerPredictions


@dataclass
class BettingRecommendation:
    """A single betting recommendation."""
    market: str
    selection: str
    confidence: str  # "HIGH", "MEDIUM", "LOW"
    reasoning: str
    percentage: float  # Probability percentage
    real_odds: Optional[float] = None  # Real odds from bookmakers
    bookmaker: Optional[str] = None  # Bookmaker name
    value_rating: Optional[str] = None  # "EXCELLENT", "GOOD", "FAIR", "POOR"
    odds_range: Optional[str] = None  # DEPRECATO: mantenuto per compatibilità


@dataclass
class ExactScorePrediction:
    """Exact score prediction."""
    score: str  # e.g., "1-0"
    probability: float
    reasoning: str
    odds_estimate: str


@dataclass
class MatchBettingAnalysis:
    """Complete betting analysis for a match."""
    match_info: str
    recommendations: List[BettingRecommendation]
    exact_scores: List[ExactScorePrediction]
    summary: Dict[str, str]
    player_predictions: Optional[MatchPlayerPredictions] = None
