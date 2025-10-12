"""Core modules for the footy predictor application."""

from .models import Team, Fixture, TeamStats, MatchPrediction
from .config import get_settings

__all__ = [
    "Team", "Fixture", "TeamStats", "MatchPrediction",
    "get_settings"
]