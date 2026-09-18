"""Player-to-be-booked odds: parsing, bookmaker priority and batch fetching."""

import asyncio
import re
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Tuple

from core.odds_markets import BATCH_PAUSE_SECONDS, BATCH_SIZE, BOOKMAKER_PRIORITY
from core.odds_names import match_player_name, normalize_player_name
from core.odds_types import MarketOdds

PLAYER_BOOKED_SELECTION = "Yellow Card"

_SUFFIX_RE = re.compile(r"^(?P<name>.+?)\s*(?:[-–:]\s*|\s)(?P<side>yes|no)$", re.I)


def parse_booked_value(value: str) -> Optional[Tuple[str, bool]]:
    """Parse one odds value into (player_name, is_yes).

    Accepts "Name", "Name - Yes", "Name - No", "Name Yes". Bare "Yes"/"No"
    carry no player name and are rejected.
    """
    text = str(value or "").strip()
    if not text or text.lower() in ("yes", "no"):
        return None
    found = _SUFFIX_RE.match(text)
    if found:
        return found.group("name").strip(), found.group("side").lower() == "yes"
    return text, True


def _rank(bookmaker_id: int) -> int:
    """Lower = higher priority; non-priority bookmakers share the last rank."""
    try:
        return BOOKMAKER_PRIORITY.index(bookmaker_id)
    except ValueError:
        return len(BOOKMAKER_PRIORITY)


def select_player_quotes(bookmakers: Iterable, now: Optional[datetime] = None) -> Dict[str, MarketOdds]:
    """Pick, per player, ONE bookmaker's "Yes" quote following BOOKMAKER_PRIORITY.

    Never mixes providers. Players quoted only by non-priority bookmakers fall
    back to the first such bookmaker in payload order. Keys are normalised names.
    """
    now = now or datetime.now()
    best: Dict[str, Tuple[int, MarketOdds]] = {}
    for bookmaker in bookmakers:
        rank = _rank(bookmaker.bookmaker_id)
        for value in bookmaker.values:
            parsed = parse_booked_value(value.get("value", ""))
            if parsed is None or not parsed[1]:
                continue
            try:
                odd = float(value.get("odd", 0))
            except (TypeError, ValueError):
                continue
            key = normalize_player_name(parsed[0])
            if odd <= 1.0 or not key:
                continue
            if key in best and best[key][0] <= rank:
                continue  # already have an equal/higher priority bookmaker
            best[key] = (rank, MarketOdds(
                bookmaker_name=bookmaker.bookmaker_name, bookmaker_id=bookmaker.bookmaker_id,
                market=f"Player Card - {parsed[0]}", selection=PLAYER_BOOKED_SELECTION,
                odds=odd, last_update=now,
            ))
    return {key: quote for key, (_, quote) in best.items()}


def _to_dict(quote: MarketOdds) -> dict:
    return {**quote.__dict__, "last_update": quote.last_update.isoformat()}


def _from_dict(raw: dict) -> MarketOdds:
    return MarketOdds(**{**raw, "last_update": datetime.fromisoformat(raw["last_update"])})


class PlayerBookedOddsMixin:
    """Requires `odds_client` (OddsAPIClient) and `_cache` (OddsCache) on the host."""

    async def get_player_booked_odds(self, fixture_id: int) -> Dict[str, MarketOdds]:
        """Player-to-be-booked quotes for a fixture, keyed by normalised player name.

        Empty dict when the market is not offered or the request failed. Only
        successful lookups (including "no data") are cached; failures are retried.
        """
        cache_key = f"odds:player_booked:{fixture_id}"
        cached = await self._cache.get(cache_key)
        if cached is not self._cache.MISS:
            return {key: _from_dict(raw) for key, raw in cached.items()}

        try:
            fixture_odds = await self.odds_client.get_player_booked_odds(fixture_id)
        except Exception as exc:
            print(f"⚠️ Quote cartellini giocatore non disponibili (fixture {fixture_id}): {exc}")
            return {}

        quotes = select_player_quotes(fixture_odds.bookmakers) if fixture_odds else {}
        await self._cache.set(cache_key, {key: _to_dict(q) for key, q in quotes.items()})
        return quotes

    async def get_player_booked_odds_batch(self, fixture_ids: List[int]) -> Dict[int, Dict[str, MarketOdds]]:
        """Fetch several fixtures: at most BATCH_SIZE requests at once, pause between batches."""
        results: Dict[int, Dict[str, MarketOdds]] = {}
        for start in range(0, len(fixture_ids), BATCH_SIZE):
            chunk = fixture_ids[start:start + BATCH_SIZE]
            chunk_results = await asyncio.gather(*(self.get_player_booked_odds(fid) for fid in chunk))
            results.update(zip(chunk, chunk_results))
            if start + BATCH_SIZE < len(fixture_ids):
                await asyncio.sleep(BATCH_PAUSE_SECONDS)
        return results

    async def get_player_booked_quote(self, fixture_id: int, player_name: str) -> Optional[MarketOdds]:
        """Quote for one player (accent/initial tolerant); None if absent or ambiguous."""
        quotes = await self.get_player_booked_odds(fixture_id)
        matched = match_player_name(player_name, quotes.keys())
        return quotes.get(normalize_player_name(matched)) if matched else None
