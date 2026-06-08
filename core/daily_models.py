"""Daily analysis data models."""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from datetime import datetime


@dataclass
class DailyPick:
    """Individual betting pick with confidence and metadata."""
    match_id: int
    home_team: str
    away_team: str
    market: str
    selection: str
    confidence: str
    percentage: float
    reasoning: str
    match_time: datetime
    league: str
    real_odds: Optional[float] = None
    bookmaker: Optional[str] = None
    player_team: Optional[str] = None
    # Edge / Kelly fields (populated when real_odds is available)
    edge: Optional[float] = None
    ev_percent: Optional[float] = None
    kelly_quarter: Optional[float] = None
    verdict: Optional[str] = None
    odds_range: Optional[str] = None  # DEPRECATO
    
    @property
    def confidence_score(self) -> float:
        """Convert confidence to numeric score for ranking."""
        return {
            "HIGH": 90.0,
            "MEDIUM": 70.0,
            "LOW": 50.0
        }.get(self.confidence, 50.0) + (self.percentage / 10)


@dataclass
class BettingCombination:
    """A combination of betting picks."""
    picks: List[DailyPick]
    confidence: float
    estimated_odds: float
    description: str


@dataclass
class DailyLeagueAnalysis:
    """Comprehensive analysis for a full league matchday."""
    league_name: str
    country_flag: str
    round_number: int
    total_matches_analyzed: int
    total_picks_generated: int
    analysis_timestamp: datetime
    top_picks: List[DailyPick]
    optimal_combinations: List[BettingCombination]
    summary_stats: Dict[str, Any]
    best_category_picks: Dict[str, DailyPick]
    recommended_strategy: str
    top_player_cards_picks: Optional[List[DailyPick]] = None  # Top 8 individual player card predictions
