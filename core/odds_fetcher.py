"""
Odds Fetcher Module - Gestisce il recupero delle quote dai bookmaker.

Questo modulo:
1. Fetcha le quote da tutti i bookmaker disponibili
2. Assegna la quota secondo la priorita' Bet365 > Bwin > William Hill > Betfair
   (fallback al primo bookmaker disponibile solo se nessuno dei 4 quota il mercato)
3. Mappa i mercati ai bet id verificati (core/odds_markets.py, SSOT); nessun id = nessuna quota
4. Cache TTL 600s con degrado offline (core/odds_cache.py)
"""

import asyncio
import re
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple

from adapters.odds_api import OddsAPIClient
from core.config import get_settings
from core.odds_cache import OddsCache
from core.odds_markets import (
    BATCH_PAUSE_SECONDS, BATCH_SIZE, BOOKMAKER_PRIORITY, ODDS_CACHE_TTL,
    parse_player_card_market, resolve_bet_id, split_team_market,
)
from core.odds_names import normalize_player_name
from core.odds_player_booked import PlayerBookedOddsMixin
from core.odds_types import MarketOdds
from utils.redis_cache import get_redis_cache

__all__ = ["OddsFetcher", "MarketOdds"]

_DEFAULT_REDIS = object()


class OddsFetcher(PlayerBookedOddsMixin):
    """
    Fetcher per le quote dei bookmaker.

    - La quota di un pick segue BOOKMAKER_PRIORITY e traccia il bookmaker reale
    - Il confronto con la miglior quota di mercato resta solo informativo
    - Mercati senza bet id verificato (es. tiri per squadra) -> None, un warning per run
    """

    def __init__(self, odds_client=None, redis_cache=_DEFAULT_REDIS):
        """`redis_cache=None` disables Redis (memory-only); default = shared Redis singleton."""
        self.settings = get_settings() if odds_client is None else None
        self.odds_client = odds_client or OddsAPIClient()
        self.redis_cache = get_redis_cache() if redis_cache is _DEFAULT_REDIS else redis_cache
        self._cache = OddsCache(self.redis_cache, ODDS_CACHE_TTL)
        self.cache_ttl = ODDS_CACHE_TTL
        self.preferred_bookmakers = list(BOOKMAKER_PRIORITY)
        self._warned: Set[str] = set()
        self._fixture_teams: Dict[int, Tuple[str, str]] = {}

    async def initialize(self):
        """Inizializza il fetcher recuperando bookmaker e bet disponibili."""
        try:
            await self.odds_client.get_bookmakers()
            await self.odds_client.get_available_bets()
            print("✅ Odds Fetcher pronto!")
            return True
        except Exception as e:
            print(f"⚠️ Errore durante l'inizializzazione: {e}")
            return False

    def _warn_once(self, key: str, message: str) -> None:
        """Print a warning only the first time `key` is seen in this run."""
        if key not in self._warned:
            self._warned.add(key)
            print(message)

    async def _resolve_side(self, fixture_id: int, team_name: str) -> Optional[str]:
        """Return "home"/"away" for `team_name` in the fixture (1 cached API call)."""
        if fixture_id not in self._fixture_teams:
            try:
                teams = await self.odds_client.get_fixture_teams(fixture_id)
            except Exception as exc:
                print(f"⚠️ Squadre fixture {fixture_id} non recuperabili: {exc}")
                return None
            if not teams:
                return None
            self._fixture_teams[fixture_id] = teams
        home, away = self._fixture_teams[fixture_id]
        target = normalize_player_name(team_name)
        if target == normalize_player_name(home):
            return "home"
        if target == normalize_player_name(away):
            return "away"
        return None

    async def get_odds_for_market(self, fixture_id: int, market: str, selection: str) -> Optional[MarketOdds]:
        """
        Recupera la quota per un mercato specifico.

        Returns:
            MarketOdds (un solo bookmaker, per priorita') o None se non disponibile
        """
        player_name = parse_player_card_market(market)
        if player_name is not None:
            return await self.get_player_booked_quote(fixture_id, player_name)

        cache_key = f"odds:{fixture_id}:{market}:{selection}"
        cached = await self._cache.get(cache_key)
        if cached is not self._cache.MISS and isinstance(cached, dict):
            return MarketOdds(**{**cached, "last_update": datetime.fromisoformat(cached["last_update"])})

        side = None
        team_market = split_team_market(market)
        if team_market is not None:
            side = await self._resolve_side(fixture_id, team_market[0])
        bet_id = self._get_bet_id_for_market(market, side)
        if not bet_id:
            kind = f"team {team_market[1]}" if team_market else market
            self._warn_once(f"nobet:{kind}", f"⚠️ Nessun bet id verificato per mercato: {kind} (nessuna quota)")
            return None

        try:
            result = await self._fetch_from_bookmakers(fixture_id, bet_id, selection)
        except Exception as e:
            print(f"⚠️ Errore recupero quote per {market} - {selection}: {e}")
            return None
        if not result:
            print(f"   ⚠️  Nessuna quota disponibile per {market}: {selection} (fixture {fixture_id})")
            return None

        market_odds = MarketOdds(
            bookmaker_name=result[0], bookmaker_id=result[1], market=market,
            selection=selection, odds=result[2], last_update=datetime.now(),
        )
        await self._cache.set(cache_key, {**market_odds.__dict__, "last_update": market_odds.last_update.isoformat()})
        return market_odds

    async def get_odds_for_multiple_picks(self, fixture_id: int, picks: List[Tuple[str, str]]) -> Dict[str, Optional[MarketOdds]]:
        """Recupera quote per piu' picks: max BATCH_SIZE richieste alla volta, con pausa tra batch."""
        print(f"\n💰 Recupero quote per {len(picks)} mercati...")
        tasks = [(f"{m}:{s}", self.get_odds_for_market(fixture_id, m, s)) for m, s in picks]
        results: Dict[str, Optional[MarketOdds]] = {}

        for i in range(0, len(tasks), BATCH_SIZE):
            batch = tasks[i:i + BATCH_SIZE]
            batch_results = await asyncio.gather(*[task for _, task in batch], return_exceptions=True)
            for (key, _), result in zip(batch, batch_results):
                if isinstance(result, Exception):
                    print(f"⚠️ Errore per {key}: {result}")
                    results[key] = None
                else:
                    results[key] = result
            if i + BATCH_SIZE < len(tasks):
                await asyncio.sleep(BATCH_PAUSE_SECONDS)
        return results

    @staticmethod
    def _bookmaker_rank(bookmaker_id: int) -> int:
        try:
            return BOOKMAKER_PRIORITY.index(bookmaker_id)
        except ValueError:
            return len(BOOKMAKER_PRIORITY)

    async def _fetch_from_bookmakers(self, fixture_id: int, bet_id: int, selection: str) -> Optional[Tuple[str, int, float]]:
        """
        Fetcha le quote e ritorna quella del bookmaker a priorita' piu' alta.

        Priorita' Bet365 > Bwin > William Hill > Betfair; se nessuno dei 4 quota
        la selezione, il primo bookmaker disponibile nel payload. La miglior
        quota di mercato e' solo informativa (log).

        Returns:
            Tuple (bookmaker_name, bookmaker_id, odds) o None
        """
        fixture_odds = await self.odds_client.get_fixture_odds(
            fixture_id=fixture_id, bet_ids=[bet_id], bookmaker_ids=None
        )
        if not fixture_odds or not fixture_odds.bookmakers:
            return None

        quotes: List[Tuple[str, int, float]] = []
        for bookmaker_odds in fixture_odds.bookmakers:
            for value in bookmaker_odds.values:
                if not self._match_selection(value.get("value", ""), selection):
                    continue
                try:
                    odds_value = float(value.get("odd", 0))
                except (TypeError, ValueError):
                    continue
                if odds_value > 0:
                    quotes.append((bookmaker_odds.bookmaker_name, bookmaker_odds.bookmaker_id, odds_value))
                    break  # one quote per bookmaker for this selection
        if not quotes:
            return None

        # sorted() is stable: ties keep payload order, so the fallback is "first available".
        chosen = sorted(quotes, key=lambda q: self._bookmaker_rank(q[1]))[0]
        market_best = max(quotes, key=lambda q: q[2])
        if market_best[1] != chosen[1]:
            print(f"   ℹ️  Quota assegnata {chosen[0]}:{chosen[2]:.2f} (miglior quota mercato: {market_best[0]}:{market_best[2]:.2f})")
        return chosen

    def _get_bet_id_for_market(self, market: str, side: Optional[str] = None) -> Optional[int]:
        """
        Mappa il nome del nostro mercato al bet_id verificato (core/odds_markets.py).

        Args:
            market: es. "Match Goals", "Inter Corners", "Player Card - L. Martinez"
            side: "home"/"away" = lato della squadra nei mercati per-squadra

        Returns:
            bet_id oppure None (mercati per-squadra senza side, mercati giocatore,
            mercati senza bet id come i tiri per squadra)
        """
        return resolve_bet_id(market, side)

    def _match_selection(self, api_value: str, our_selection: str) -> bool:
        """
        Verifica se il valore dell'API corrisponde alla nostra selezione.
        
        Args:
            api_value: Valore dall'API (es. "Over 2.5", "Home", "Yes")
            our_selection: Nostra selezione (es. "Over 2.5", "1 (Home Win)", "Yes")
        
        Returns:
            True se corrispondono
        """
        api_lower = api_value.lower().strip()
        our_lower = our_selection.lower().strip()
        
        # Match diretto
        if api_lower == our_lower:
            return True
        
        # Match Over/Under con numeri
        if "over" in our_lower and "over" in api_lower:
            our_num = self._extract_number(our_lower)
            api_num = self._extract_number(api_lower)
            if our_num and api_num and abs(our_num - api_num) < 0.1:
                return True
        
        if "under" in our_lower and "under" in api_lower:
            our_num = self._extract_number(our_lower)
            api_num = self._extract_number(api_lower)
            if our_num and api_num and abs(our_num - api_num) < 0.1:
                return True
        
        # Match Result variations
        if ("home" in our_lower or "1" in our_lower) and "home" in api_lower:
            return True
        if ("away" in our_lower or "2" in our_lower) and "away" in api_lower:
            return True
        if ("draw" in our_lower or "x" in our_lower) and "draw" in api_lower:
            return True
        
        # BTTS variations
        if "yes" in our_lower and "yes" in api_lower:
            return True
        if "no" in our_lower and "no" in api_lower:
            return True
        
        return False
    
    def _extract_number(self, text: str) -> Optional[float]:
        """Estrae il numero da una stringa."""
        match = re.search(r'\d+\.?\d*', text)
        if match:
            return float(match.group())
        return None
    
    async def get_all_odds_for_fixture(self, fixture_id: int) -> Dict[str, List[MarketOdds]]:
        """Recupera le quote dei mercati principali (esplorazione): mercato -> quote per bookmaker."""
        print(f"\n🔍 Recupero tutte le quote per fixture {fixture_id}...")
        all_odds: Dict[str, List[MarketOdds]] = {}
        main_bets = [1, 5, 8, 10, 80, 45]  # Winner, Goals, BTTS, Score, Cards, Corners

        for bet_id in main_bets:
            try:
                fixture_odds = await self.odds_client.get_fixture_odds(fixture_id=fixture_id, bet_ids=[bet_id])
                for bm in (fixture_odds.bookmakers if fixture_odds else []):
                    bucket = all_odds.setdefault(bm.bet_name, [])
                    for value in bm.values:
                        bucket.append(MarketOdds(
                            bookmaker_name=bm.bookmaker_name, bookmaker_id=bm.bookmaker_id,
                            market=bm.bet_name, selection=value.get("value", ""),
                            odds=float(value.get("odd", 0)), last_update=datetime.now(),
                        ))
                await asyncio.sleep(BATCH_PAUSE_SECONDS / 3)
            except Exception:
                continue

        print(f"✅ Trovati {len(all_odds)} mercati con quote")
        return all_odds

    def clear_cache(self):
        """Svuota la cache in-process (le entry Redis scadono da sole dopo il TTL)."""
        self._cache._memory.clear()
        print("🧹 Cache quote pulita")
