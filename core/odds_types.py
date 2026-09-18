"""Shared odds data types."""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class MarketOdds:
    """Quote per un mercato specifico (una sola quota, di un solo bookmaker)."""
    bookmaker_name: str
    bookmaker_id: int
    market: str
    selection: str
    odds: float
    last_update: datetime
