"""Single source of truth for API-Football bet ids and bookmaker priority.

Every id below was verified against a real `/odds?fixture=` payload
(Serie A 2026, fixture 1550128) -- see docs/ODDS_FETCHER.md. A market with no
verified bet id maps to None: better no quote than a wrong one.
"""

import re
from typing import Dict, Optional, Tuple

# Bookmaker ids as they appear in the payload: Bet365=8, Bwin=6, William Hill=7, Betfair=3.
# Order IS the priority (rule 11).
BOOKMAKER_PRIORITY: Tuple[int, ...] = (8, 6, 7, 3)

# Rate limiting (rule 10).
BATCH_SIZE = 5
BATCH_PAUSE_SECONDS = 1.0

# Odds cache TTL (seconds).
ODDS_CACHE_TTL = 600

# "Player to be booked": API-Football exposes two bet ids with that name.
PLAYER_BOOKED_BET_IDS: Tuple[int, ...] = (102, 251)

# Whole-match markets, keyed by lowercase market name / alias.
MATCH_BET_IDS: Dict[str, int] = {
    "match_winner": 1, "1x2": 1, "match result": 1,
    "goals_over_under": 5, "match_goals": 5, "match goals": 5,
    "btts": 8, "both_teams_to_score": 8, "both teams to score": 8,
    "correct_score": 10, "exact_score": 10, "exact score": 10,
    "double_chance": 12, "double chance": 12,
    "corners": 45, "total_corners": 45, "total corners": 45,       # 'Corners Over Under'
    "cards": 80, "total_cards": 80, "total cards": 80,             # 'Cards Over/Under'
    "total_shots": 211, "total shots": 211,                        # 'Total Shots'
    "total_shots_on_goal": 87, "total shots on goal": 87,          # 'Total ShotOnGoal'
}

# Per-team markets: metric -> (home bet id, away bet id). None = no team-level
# bet exists (shots 240/241/269/275/276 are per PLAYER, not per team).
TEAM_BET_IDS: Dict[str, Tuple[Optional[int], Optional[int]]] = {
    "corners": (57, 58),        # Home/Away Corners Over/Under
    "cards": (82, 83),          # Home/Away Team Total Cards
    "goals": (16, 17),          # Total - Home / Total - Away
    "shots": (None, None),
    "shots on goal": (None, None),
}

_TEAM_MARKET_RE = re.compile(r"^(?P<team>.+?)\s+(?P<metric>shots on goal|shots|corners|cards|goals)$", re.I)
_PLAYER_CARD_RE = re.compile(r"^player cards?\s*[-:]\s*(?P<name>.+)$", re.I)


def split_team_market(market: str) -> Optional[Tuple[str, str]]:
    """Split "<Team> Corners" into (team, "corners"); None for whole-match markets."""
    match = _TEAM_MARKET_RE.match(market.strip())
    if not match:
        return None
    team = match.group("team").strip()
    if team.lower() in {"total", "match", "both teams"}:
        return None
    return team, match.group("metric").lower()


def parse_player_card_market(market: str) -> Optional[str]:
    """Return the player name of a "Player Card - <name>" market, else None."""
    match = _PLAYER_CARD_RE.match(market.strip())
    return match.group("name").strip() if match else None


def resolve_bet_id(market: str, side: Optional[str] = None) -> Optional[int]:
    """Map one of our market names to an API bet id (None if no verified id).

    `side` ("home"/"away") is needed only for per-team markets. Player markets
    are never resolved here (they use PLAYER_BOOKED_BET_IDS).
    """
    lower = market.strip().lower()
    if parse_player_card_market(market) is not None or lower.startswith("player"):
        return None
    if lower in MATCH_BET_IDS:
        return MATCH_BET_IDS[lower]

    team_market = split_team_market(market)
    if team_market is not None:
        ids = TEAM_BET_IDS.get(team_market[1])
        if ids is None or side not in ("home", "away"):
            return None
        return ids[0] if side == "home" else ids[1]

    if "btts" in lower or "both teams" in lower:
        return 8
    if "exact" in lower and "score" in lower:
        return 10
    if "goal" in lower and ("over" in lower or "under" in lower or "match" in lower):
        return 5
    if "result" in lower or "winner" in lower or "1x2" in lower:
        return 1
    return None
