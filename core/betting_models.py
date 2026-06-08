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
    percentage: float  # Probability percentage (0-100)
    real_odds: Optional[float] = None   # Real odds from bookmakers
    bookmaker: Optional[str] = None     # Bookmaker name
    # Edge / Kelly fields (populated when real_odds is available)
    edge: Optional[float] = None        # Our prob - implied prob (es. 0.12 = +12%)
    ev_percent: Optional[float] = None  # Expected Value % (es. +11.5)
    kelly_quarter: Optional[float] = None  # Quarter Kelly fraction (es. 0.031 = 3.1%)
    verdict: Optional[str] = None       # "BET" | "VALUE" | "PASS"
    # Legacy (never used, kept for dataclass compatibility)
    value_rating: Optional[str] = None
    odds_range: Optional[str] = None


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
