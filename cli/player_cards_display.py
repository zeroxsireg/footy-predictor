"""
Player cards display — top booking-risk players with real odds when available.

Rendering only; odds are supplied by OddsFetcher.get_player_booked_odds
(hook: apply_player_odds).
"""

import logging
import re
from typing import Any, Dict, Iterable, Optional

from cli.betting_render import format_quote_lines

logger = logging.getLogger(__name__)


def normalize_player_name(name: str) -> str:
    """Lowercase, strip accents-agnostic punctuation/spaces for odds lookup."""
    return re.sub(r"[^a-z0-9]+", " ", (name or "").lower()).strip()


def apply_player_odds(picks: Iterable[Any], player_odds: Optional[Dict[str, Any]]) -> None:
    """
    Hook: attach real odds to player picks and compute edge/EV/Kelly.

    player_odds: Dict[normalized player name, MarketOdds] as returned by
    OddsFetcher.get_player_booked_odds(fixture_id). None/empty -> no-op.
    """
    if not player_odds:
        return
    from core.edge_calculator import evaluate_bet

    lookup = {normalize_player_name(k): v for k, v in player_odds.items()}
    for pick in picks:
        name = normalize_player_name((pick.market or "").replace("Player Card - ", ""))
        market_odds = lookup.get(name)
        if market_odds is None or not getattr(market_odds, "odds", None):
            continue
        pick.real_odds = market_odds.odds
        pick.bookmaker = market_odds.bookmaker_name
        decision = evaluate_bet(pick.percentage, pick.real_odds)
        pick.edge = decision.edge
        pick.ev_percent = decision.ev_percent
        pick.kelly_quarter = decision.kelly_quarter
        pick.verdict = decision.verdict


def render_player_cards(picks, limit: int = 5) -> None:
    """Print player card picks (or one explicit line when there are none)."""
    top_picks = list(picks or [])[:limit]
    if not top_picks:
        print("\n🟨 Cartellini giocatore: nessun dato rosa disponibile (Redis offline?)")
        return

    print(f"\n🟨 TOP {len(top_picks)} GIOCATORI A RISCHIO AMMONIZIONE:")
    print("═" * 60)
    for i, pick in enumerate(top_picks, 1):
        conf_emoji = "🔥" if pick.confidence == "HIGH" else "⚡" if pick.confidence == "MEDIUM" else "💡"
        player_name = (pick.market or "").replace("Player Card - ", "")
        pct = pick.percentage or 0.0
        pct_color = "🔴" if pct >= 75 else "🟠" if pct >= 60 else "🟡"
        print(f" {i}. {conf_emoji} {player_name}")
        if getattr(pick, "player_team", None):
            print(f"    🏟️  {pick.player_team}")
        for line in format_quote_lines(pick, pct_color):
            print(f"    {line}")
        print(f"    💬 {pick.reasoning}")
        print()
    print("─" * 60)


async def display_player_cards_picks(
    fixture, prediction, player_card_analyzer, api_client,
    league_id, season, league_name="Unknown League", odds_fetcher=None,
):
    """Analyze and display top player cards picks for a match."""
    try:
        from analyzers.player_cards_analyzer import PlayerCardsAnalyzer
        analyzer = PlayerCardsAnalyzer()
        picks = await analyzer.analyze_match_players(fixture, [], league_name, api_client)
        if picks and odds_fetcher is not None and hasattr(odds_fetcher, "get_player_booked_odds"):
            fixture_id = getattr(fixture, "id", None)
            if fixture_id:
                apply_player_odds(picks, await odds_fetcher.get_player_booked_odds(fixture_id))
        render_player_cards(picks)
    except Exception as exc:  # display must never crash the matchday run
        logger.warning("Player cards display failed: %s", exc)
        print(f"⚠️  Player cards analysis unavailable: {exc}")
