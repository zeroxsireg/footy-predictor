"""Data models for the footy predictor CLI."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any


@dataclass
class Team:
    """Team information."""
    id: int
    name: str
    logo: Optional[str] = None


@dataclass
class Fixture:
    """Match fixture information."""
    id: int
    date: datetime
    status: str
    home_team: Team
    away_team: Team
    venue: Optional[str] = None


@dataclass
class TeamStats:
    """Team statistics for a season."""
    team: Team
    matches_played: int
    wins: int
    draws: int
    losses: int
    goals_for: int
    goals_against: int
    shots_total: int
    shots_on_target: int
    corners: int
    yellow_cards: int
    red_cards: int
    # Additional statistics from API
    form: str = ""  # Recent form (e.g., "WLDWL")
    clean_sheets: int = 0  # Matches without conceding
    failed_to_score: int = 0  # Matches without scoring
    penalties_scored: int = 0
    penalties_missed: int = 0
    biggest_win_margin: int = 0
    biggest_loss_margin: int = 0
    # Under/Over statistics for goals scored
    over_1_5_goals: int = 0  # Matches with over 1.5 goals scored
    over_2_5_goals: int = 0  # Matches with over 2.5 goals scored
    over_3_5_goals: int = 0  # Matches with over 3.5 goals scored
    # Under/Over statistics for goals conceded
    over_1_5_conceded: int = 0  # Matches with over 1.5 goals conceded
    over_2_5_conceded: int = 0  # Matches with over 2.5 goals conceded
    over_3_5_conceded: int = 0  # Matches with over 3.5 goals conceded
    
    @property
    def goals_per_game(self) -> float:
        """Goals scored per game."""
        return self.goals_for / self.matches_played if self.matches_played > 0 else 0.0
    
    @property
    def goals_conceded_per_game(self) -> float:
        """Goals conceded per game."""
        return self.goals_against / self.matches_played if self.matches_played > 0 else 0.0
    
    @property
    def shots_per_game(self) -> float:
        """Shots per game."""
        return self.shots_total / self.matches_played if self.matches_played > 0 else 0.0
    
    @property
    def shots_on_target_per_game(self) -> float:
        """Shots on target per game."""
        return self.shots_on_target / self.matches_played if self.matches_played > 0 else 0.0
    
    @property
    def corners_per_game(self) -> float:
        """Corners per game."""
        return self.corners / self.matches_played if self.matches_played > 0 else 0.0
    
    @property
    def yellow_cards_per_game(self) -> float:
        """Yellow cards per game."""
        return self.yellow_cards / self.matches_played if self.matches_played > 0 else 0.0
    
    @property
    def clean_sheet_percentage(self) -> float:
        """Clean sheet percentage."""
        return (self.clean_sheets / self.matches_played * 100) if self.matches_played > 0 else 0.0
    
    @property
    def failed_to_score_percentage(self) -> float:
        """Failed to score percentage."""
        return (self.failed_to_score / self.matches_played * 100) if self.matches_played > 0 else 0.0
    
    @property
    def penalty_conversion_rate(self) -> float:
        """Penalty conversion rate percentage."""
        total_penalties = self.penalties_scored + self.penalties_missed
        return (self.penalties_scored / total_penalties * 100) if total_penalties > 0 else 0.0
    
    @property
    def recent_form_points(self) -> int:
        """Calculate points from recent form (W=3, D=1, L=0)."""
        if not self.form:
            return 0
        points = 0
        for result in self.form[-5:]:  # Last 5 matches
            if result == 'W':
                points += 3
            elif result == 'D':
                points += 1
        return points
    
    @property
    def over_1_5_goals_percentage(self) -> float:
        """Percentage of matches with over 1.5 goals scored."""
        return (self.over_1_5_goals / self.matches_played * 100) if self.matches_played > 0 else 0.0
    
    @property
    def over_2_5_goals_percentage(self) -> float:
        """Percentage of matches with over 2.5 goals scored."""
        return (self.over_2_5_goals / self.matches_played * 100) if self.matches_played > 0 else 0.0
    
    @property
    def over_3_5_goals_percentage(self) -> float:
        """Percentage of matches with over 3.5 goals scored."""
        return (self.over_3_5_goals / self.matches_played * 100) if self.matches_played > 0 else 0.0
    
    @property
    def over_1_5_conceded_percentage(self) -> float:
        """Percentage of matches with over 1.5 goals conceded."""
        return (self.over_1_5_conceded / self.matches_played * 100) if self.matches_played > 0 else 0.0
    
    @property
    def over_2_5_conceded_percentage(self) -> float:
        """Percentage of matches with over 2.5 goals conceded."""
        return (self.over_2_5_conceded / self.matches_played * 100) if self.matches_played > 0 else 0.0
    
    @property
    def over_3_5_conceded_percentage(self) -> float:
        """Percentage of matches with over 3.5 goals conceded."""
        return (self.over_3_5_conceded / self.matches_played * 100) if self.matches_played > 0 else 0.0


@dataclass
class MatchPrediction:
    """Match prediction data."""
    fixture: Fixture
    home_stats: TeamStats
    away_stats: TeamStats
    expected_total_goals: float
    expected_total_corners: float
    expected_total_yellow_cards: float
