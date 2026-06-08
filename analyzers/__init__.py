"""
Analyzers Package — Betting market analysis modules.

Each analyzer handles exactly one market type and is registered here.
To disable a market: set its value to None or remove the entry.
To add a new market: create the class and add an entry below — nothing
else needs to change.
"""

from typing import Dict, Optional, Type

from .base import BaseAnalyzer
from .goals_analyzer import GoalsAnalyzer
from .shots_analyzer import ShotsAnalyzer
from .corners_analyzer import CornersAnalyzer
from .cards_analyzer import CardsAnalyzer
from .result_analyzer import ResultAnalyzer
from .score_analyzer import ScoreAnalyzer
from .player_cards_analyzer import PlayerCardsAnalyzer

# ── Plugin registry ───────────────────────────────────────────────────────────
# Keys are used as stable identifiers (logging, config overrides, etc.).
# Set a value to None to disable that market without deleting code.

ANALYZER_REGISTRY: Dict[str, Optional[Type[BaseAnalyzer]]] = {
    "goals":   GoalsAnalyzer,
    "shots":   ShotsAnalyzer,
    "corners": CornersAnalyzer,
    "cards":   CardsAnalyzer,
    "result":  ResultAnalyzer,
}

__all__ = [
    "BaseAnalyzer",
    "GoalsAnalyzer",
    "ShotsAnalyzer",
    "CornersAnalyzer",
    "CardsAnalyzer",
    "ResultAnalyzer",
    "ScoreAnalyzer",
    "PlayerCardsAnalyzer",
    "ANALYZER_REGISTRY",
]
