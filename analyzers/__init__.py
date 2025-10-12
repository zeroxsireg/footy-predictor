"""
Analyzers Package - Moduli di analisi separati per mercati betting.

Ogni analyzer è responsabile di UN solo tipo di mercato.
"""

from .base import BaseAnalyzer
from .goals_analyzer import GoalsAnalyzer
from .shots_analyzer import ShotsAnalyzer
from .corners_analyzer import CornersAnalyzer
from .cards_analyzer import CardsAnalyzer
from .result_analyzer import ResultAnalyzer
from .score_analyzer import ScoreAnalyzer
from .player_cards_analyzer import PlayerCardsAnalyzer

__all__ = [
    'BaseAnalyzer',
    'GoalsAnalyzer',
    'ShotsAnalyzer',
    'CornersAnalyzer',
    'CardsAnalyzer',
    'ResultAnalyzer',
    'ScoreAnalyzer',
    'PlayerCardsAnalyzer'
]

