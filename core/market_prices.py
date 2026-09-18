"""Quotes for the lean pipeline: 1X2 and Over/Under 2.5, ONE bookmaker per market.

Rule 11: Bet365 > Bwin > William Hill > Betfair; the selections of a market never
come from different bookmakers. Benchmark prices come only from Pinnacle (id 4).
Payload structure verified on fixture 1550135 (docs/ODDS_FETCHER.md).
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core.contracts import MARKET_1X2, MARKET_OU25, PriceQuote
from core.market_http import api_get, cached
from core.odds_markets import BOOKMAKER_PRIORITY, ODDS_CACHE_TTL

PINNACLE_ID = 4
_BET_1X2, _BET_OU = 1, 5
_1X2_LABELS = {"Home": "1", "Draw": "X", "Away": "2"}
_OU25_LABELS = {"Over 2.5": "over", "Under 2.5": "under"}
_MARKETS = {  # market -> (bet id, label map)
    MARKET_1X2: (_BET_1X2, _1X2_LABELS),
    MARKET_OU25: (_BET_OU, _OU25_LABELS),
}


def _parse_market(bookmaker: Dict[str, Any], bet_id: int, labels: Dict[str, str]) -> Optional[Dict[str, float]]:
    """Odds of `bet_id` if the bookmaker quotes EVERY selection with a valid price."""
    for bet in bookmaker.get("bets", []):
        if bet.get("id") != bet_id:
            continue
        odds: Dict[str, float] = {}
        for value in bet.get("values", []):
            key = labels.get(value.get("value"))
            try:
                price = float(value.get("odd"))
            except (TypeError, ValueError):
                continue
            if key is not None and price > 1.0:
                odds[key] = price
        return odds if len(odds) == len(labels) else None
    return None


def _quote(fixture_id: int, market: str, bookmaker: Dict[str, Any], odds: Dict[str, float]) -> PriceQuote:
    return PriceQuote(fixture_id=fixture_id, market=market, bookmaker=bookmaker.get("name", ""),
                      bookmaker_id=bookmaker["id"], odds=odds, captured_at=datetime.now(timezone.utc))


def select_quotes(fixture_id: int, bookmakers: List[Dict[str, Any]]) -> Dict[str, PriceQuote]:
    """Best-priority single-bookmaker quote per market; fallback = first complete bookmaker."""
    by_id = {b.get("id"): b for b in bookmakers}
    result: Dict[str, PriceQuote] = {}
    for market, (bet_id, labels) in _MARKETS.items():
        ordered = [by_id[i] for i in BOOKMAKER_PRIORITY if i in by_id]
        ordered += [b for b in bookmakers if b.get("id") not in BOOKMAKER_PRIORITY]
        for bookmaker in ordered:
            odds = _parse_market(bookmaker, bet_id, labels)
            if odds:
                result[market] = _quote(fixture_id, market, bookmaker, odds)
                break
    return result


def select_benchmark(fixture_id: int, bookmakers: List[Dict[str, Any]]) -> Dict[str, PriceQuote]:
    """Pinnacle-only quotes; a market Pinnacle does not quote is simply absent."""
    result: Dict[str, PriceQuote] = {}
    pinnacle = next((b for b in bookmakers if b.get("id") == PINNACLE_ID), None)
    if pinnacle is None:
        return result
    for market, (bet_id, labels) in _MARKETS.items():
        odds = _parse_market(pinnacle, bet_id, labels)
        if odds:
            result[market] = _quote(fixture_id, market, pinnacle, odds)
    return result


async def fetch_bookmakers(fixture_id: int) -> Optional[List[Dict[str, Any]]]:
    """Raw bookmaker list of a fixture (one /odds call, cached 600s); None on API failure."""
    async def load():
        response = await api_get("/odds", {"fixture": fixture_id})
        if response is None:
            return None
        return response[0].get("bookmakers", []) if response else []
    return await cached(f"mkt:odds:{fixture_id}", "live_odds", load, max_age=ODDS_CACHE_TTL)
