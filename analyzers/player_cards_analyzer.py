"""
Player Cards Analyzer - P(player is booked) for individual players.

Pure probability estimation (rule 6): no odds/stake logic here. The estimator is
the shared model in core/player_card_model.py (same one backtested by
backtest/player_cards.py): position prior + shrunk own booking rate + fouls.
Players with few appearances collapse toward the position prior; goalkeepers
and players without minutes are skipped. Each squad player's current-season
totals are added to the previous season's (same setup as the backtest, which
used one prior season of history): early in a season the current totals alone
carry no signal.
"""

from typing import Dict, List, Optional

from .base import BaseAnalyzer
from core.models import TeamStats, Fixture
from core.betting_models import BettingRecommendation
from core.daily_models import DailyPick
from core.player_card_model import live_probability

try:  # Provided by the roster service; guarded so the analyzer never crashes on import.
    from adapters.roster_service import get_team_roster_with_fallback
except ImportError:  # pragma: no cover - depends on the parallel roster work
    get_team_roster_with_fallback = None

EUROPEAN_CUPS = ("champions league", "europa league", "conference league")
MIN_PICK_PROBABILITY = 0.15   # ~ league average booking rate; below = no signal
HIGH_PROBABILITY = 0.28       # relative tiers: model probabilities top out near 0.4
MEDIUM_PROBABILITY = 0.20
MAX_PICKS = 8
HISTORY_SEASONS_BACK = 1      # previous season added to the current one (validated setup)


def merge_roster_history(current: List[Dict], previous: List[Dict]) -> List[Dict]:
    """Add the previous season's totals to each current-squad player (matched by id).

    Players who left the club (only in `previous`) are ignored. Fouls are a total over
    the appearances, so they are kept only when every season with appearances reports
    them; otherwise 0, which the analyzer treats as missing.
    """
    old_by_id = {p.get("id"): p for p in previous or [] if p.get("id") is not None}
    merged = []
    for player in current or []:
        old = old_by_id.get(player.get("id"))
        if not old:
            merged.append(player)
            continue
        row = dict(player)
        for key in ("appearances", "minutes", "yellow_cards"):
            row[key] = (player.get(key) or 0) + (old.get(key) or 0)
        cur_fouls, old_fouls = player.get("fouls_committed") or 0, old.get("fouls_committed") or 0
        complete = (cur_fouls or not (player.get("appearances") or 0)) and \
                   (old_fouls or not (old.get("appearances") or 0))
        row["fouls_committed"] = cur_fouls + old_fouls if complete else 0
        merged.append(row)
    return merged


class PlayerCardsAnalyzer(BaseAnalyzer):
    """Analyzer for individual player yellow-card probabilities."""

    def __init__(self):
        super().__init__()
        self.enabled = True

    def get_required_stats(self) -> List[str]:
        return ['yellow_cards_per_game', 'fouls_per_game']

    def analyze(self, home_stats: TeamStats, away_stats: TeamStats, **kwargs) -> List[BettingRecommendation]:
        """Team-level interface is unused: player picks come from analyze_match_players."""
        return []

    def player_probability(self, player_data: Dict) -> Optional[float]:
        """P(yellow) from roster season totals, or None if the player is out of scope."""
        if not player_data or not (player_data.get('minutes') or 0) > 0:
            return None
        fouls = player_data.get('fouls_committed') or None  # 0 = missing in roster payloads
        return live_probability(
            player_data.get('appearances') or 0,
            player_data.get('yellow_cards') or 0,
            player_data.get('position'),
            fouls=fouls,
        )

    async def _load_roster(self, api_client, team_id: int, season: int) -> List[Dict]:
        if get_team_roster_with_fallback is None:
            return []
        try:
            current = await get_team_roster_with_fallback(api_client, team_id, season) or []
        except Exception as e:
            print(f"⚠️  Roster unavailable for team {team_id}: {e}")
            return []
        if not current:
            return []
        try:
            previous = await get_team_roster_with_fallback(
                api_client, team_id, season - HISTORY_SEASONS_BACK) or []
        except Exception as e:
            print(f"⚠️  Previous-season roster unavailable for team {team_id}: {e}")
            previous = []
        return merge_roster_history(current, previous)

    def _team_picks(self, roster: List[Dict], fixture: Fixture, team_name: str,
                    league_name: str) -> List[DailyPick]:
        picks = []
        for player in roster:
            prob = self.player_probability(player)
            if prob is None or prob < MIN_PICK_PROBABILITY:
                continue
            picks.append(DailyPick(
                match_id=fixture.id,
                home_team=fixture.home_team.name,
                away_team=fixture.away_team.name,
                market=f"Player Card - {player.get('name', 'Unknown')}",
                selection="Yellow Card",
                confidence=self._tier(prob),
                percentage=prob * 100,
                odds_range=None,
                reasoning=self._reasoning(player, prob),
                match_time=fixture.date,
                league=league_name,
                real_odds=None,
                bookmaker=None,
                player_team=team_name,
            ))
        return picks

    async def analyze_match_players(self, fixture: Fixture, standings: List,
                                    league_name: str, api_client) -> List[DailyPick]:
        """Top yellow-card candidates of both teams (empty list when no roster)."""
        if not self.enabled:
            return []
        if league_name.lower() in EUROPEAN_CUPS:
            # Season totals mix league and cup: not comparable with the backtested model.
            return []
        try:
            from core.config import get_settings
            season = get_settings().default_season
            home = await self._load_roster(api_client, fixture.home_team.id, season)
            away = await self._load_roster(api_client, fixture.away_team.id, season)
            picks = (self._team_picks(home, fixture, fixture.home_team.name, league_name)
                     + self._team_picks(away, fixture, fixture.away_team.name, league_name))
            picks.sort(key=lambda p: p.percentage, reverse=True)
            return picks[:MAX_PICKS]
        except Exception as e:
            print(f"⚠️  Player cards analysis failed: {e}")
            return []

    def enable(self):
        self.enabled = True

    def disable(self):
        self.enabled = False

    @staticmethod
    def _tier(prob: float) -> str:
        return "HIGH" if prob >= HIGH_PROBABILITY else "MEDIUM" if prob >= MEDIUM_PROBABILITY else "LOW"

    @staticmethod
    def _reasoning(player: Dict, prob: float) -> str:
        apps = player.get('appearances') or 0
        yellows = player.get('yellow_cards') or 0
        fouls = player.get('fouls_committed')
        name = player.get('name', 'Player')
        text = f"{name} ({player.get('position', '?')}): {yellows} yellows in {apps} apps"
        if fouls is not None and apps:
            text += f", {fouls / apps:.1f} fouls/app"
        return text + f" (shrunk toward position prior, P={prob:.0%})"
