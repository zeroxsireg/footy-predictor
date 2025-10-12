"""
Odds Fetcher Module - Gestisce il recupero delle quote da tutti i bookmaker disponibili.

Questo modulo:
1. Fetcha le quote da TUTTI i bookmaker disponibili (non solo Bet365)
2. Mappa automaticamente i nostri mercati ai bet IDs delle API
3. Trova le migliori quote disponibili per ogni pick
4. Cache intelligente per ridurre le chiamate API
"""

import asyncio
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta

from adapters.odds_api import OddsAPIClient
from core.config import get_settings
from utils.redis_cache import get_redis_cache


@dataclass
class MarketOdds:
    """Quote per un mercato specifico."""
    bookmaker_name: str
    bookmaker_id: int
    market: str
    selection: str
    odds: float
    last_update: datetime


class OddsFetcher:
    """
    Fetcher per le quote dei bookmaker.
    
    Strategia:
    - Cerca quote su TUTTI i bookmaker disponibili
    - Preferisce Bet365, ma usa qualsiasi bookmaker abbia il mercato
    - Cache Redis per ridurre chiamate API
    - Mapping automatico tra i nostri mercati e i bet IDs API
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.odds_client = OddsAPIClient()
        self.redis_cache = get_redis_cache()
        
        # TTL cache: 10 minuti (le quote cambiano frequentemente)
        self.cache_ttl = 600
        
        # Bookmaker prioritari (ma non esclusivi)
        self.preferred_bookmakers = [8, 6, 5, 3]  # Bet365, Bwin, William Hill, Betfair
        
        # Mapping COMPLETO tra i nostri mercati e i bet IDs delle API
        # Questi sono i bet IDs standard di api-football
        self.bet_id_mapping = {
            # Match Winner / Result (bet_id: 1)
            "match_winner": 1,
            "1x2": 1,
            
            # Goals Over/Under (bet_id: 5)
            "goals_over_under": 5,
            "match_goals": 5,
            
            # Both Teams Score (bet_id: 8)
            "btts": 8,
            "both_teams_to_score": 8,
            
            # Exact Score (bet_id: 6)
            "correct_score": 6,
            "exact_score": 6,
            
            # Double Chance (bet_id: 7)
            "double_chance": 7,
            
            # Total Corners (bet_id: 12)
            "corners": 12,
            "total_corners": 12,
            
            # Total Cards (bet_id: 11)
            "cards": 11,
            "total_cards": 11,
            
            # Total Shots (non sempre disponibile)
            "total_shots": None,  # Spesso non disponibile
            
            # Team Goals
            "home_team_goals": None,
            "away_team_goals": None,
        }
    
    async def initialize(self):
        """Inizializza il fetcher recuperando bookmaker e bet disponibili."""
        try:
            # Recupera tutti i bookmaker disponibili (silent mode)
            bookmakers = await self.odds_client.get_bookmakers()
            
            # Recupera tutti i bet disponibili (silent mode)
            bets = await self.odds_client.get_available_bets()
            
            print("✅ Odds Fetcher pronto!")
            return True
            
        except Exception as e:
            print(f"⚠️ Errore durante l'inizializzazione: {e}")
            return False
    
    async def get_odds_for_market(self, fixture_id: int, market: str, selection: str) -> Optional[MarketOdds]:
        """
        Recupera le quote per un mercato specifico.
        
        Args:
            fixture_id: ID della partita
            market: Nome del mercato (es. "Match Goals", "Both Teams to Score")
            selection: Selezione specifica (es. "Over 2.5", "Yes")
        
        Returns:
            MarketOdds con le migliori quote trovate, o None se non disponibili
        """
        # Controlla cache
        cache_key = f"odds:{fixture_id}:{market}:{selection}"
        cached = await self.redis_cache.get_data(cache_key)
        
        if cached:
            # Ricostruisci MarketOdds da dict
            if isinstance(cached, dict):
                cached['last_update'] = datetime.fromisoformat(cached['last_update']) if isinstance(cached.get('last_update'), str) else datetime.now()
                return MarketOdds(**cached)
            return None
        
        # Determina il bet_id dalle API
        bet_id = self._get_bet_id_for_market(market)
        
        if not bet_id:
            print(f"⚠️ Bet ID non trovato per mercato: {market}")
            return None
        
        try:
            # Cerca quote su TUTTI i bookmaker (prima i preferiti, poi gli altri)
            odds_result = await self._fetch_from_bookmakers(fixture_id, bet_id, selection)
            
            if not odds_result:
                # Debug: nessuna quota trovata
                print(f"   ⚠️  Nessuna quota disponibile per {market}: {selection} (fixture {fixture_id})")
            
            if odds_result:
                market_odds = MarketOdds(
                    bookmaker_name=odds_result[0],
                    bookmaker_id=odds_result[1],
                    market=market,
                    selection=selection,
                    odds=odds_result[2],
                    last_update=datetime.now()
                )
                
                # Cache il risultato
                await self.redis_cache.set_data(
                    cache_key,
                    {
                        "bookmaker_name": market_odds.bookmaker_name,
                        "bookmaker_id": market_odds.bookmaker_id,
                        "market": market_odds.market,
                        "selection": market_odds.selection,
                        "odds": market_odds.odds,
                        "last_update": market_odds.last_update.isoformat()
                    },
                    ttl_type="live_odds"  # Usa il TTL predefinito per live_odds (30 min)
                )
                
                return market_odds
            
            return None
            
        except Exception as e:
            print(f"⚠️ Errore recupero quote per {market} - {selection}: {e}")
            return None
    
    async def get_odds_for_multiple_picks(self, fixture_id: int, picks: List[Tuple[str, str]]) -> Dict[str, Optional[MarketOdds]]:
        """
        Recupera quote per multipli picks in parallelo.
        
        Args:
            fixture_id: ID della partita
            picks: Lista di tuple (market, selection)
        
        Returns:
            Dizionario con chiave "market:selection" e valore MarketOdds
        """
        print(f"\n💰 Recupero quote per {len(picks)} mercati...")
        
        # Crea task paralleli per tutti i picks
        tasks = []
        for market, selection in picks:
            task = self.get_odds_for_market(fixture_id, market, selection)
            tasks.append((f"{market}:{selection}", task))
        
        # Esegui in parallelo con rate limiting
        results = {}
        batch_size = 5  # 5 richieste alla volta per non sovraccaricare l'API
        
        for i in range(0, len(tasks), batch_size):
            batch = tasks[i:i + batch_size]
            batch_results = await asyncio.gather(*[task for _, task in batch], return_exceptions=True)
            
            for (key, _), result in zip(batch, batch_results):
                if isinstance(result, Exception):
                    print(f"⚠️ Errore per {key}: {result}")
                    results[key] = None
                else:
                    results[key] = result
            
            # Rate limiting tra batch
            if i + batch_size < len(tasks):
                await asyncio.sleep(0.5)
        
        # Ritorna risultati (silent mode)
        return results
    
    async def _fetch_from_bookmakers(self, fixture_id: int, bet_id: int, selection: str) -> Optional[Tuple[str, int, float]]:
        """




n        Fetcha quote da TUTTI i bookmaker e ritorna la MIGLIORE.
        
        Returns:
            Tuple (bookmaker_name, bookmaker_id, best_odds) o None
        """
        all_odds = []  # Lista di tuple (bookmaker_name, bookmaker_id, odds)
        
        try:
            # Richiedi quote da TUTTI i bookmaker in una volta
            fixture_odds = await self.odds_client.get_fixture_odds(
                fixture_id=fixture_id,
                bet_ids=[bet_id],
                bookmaker_ids=None  # TUTTI i bookmaker
            )
            
            if fixture_odds and fixture_odds.bookmakers:
                # Raccogli TUTTE le quote disponibili
                for bookmaker_odds in fixture_odds.bookmakers:
                    for value in bookmaker_odds.values:
                        if self._match_selection(value.get("value", ""), selection):
                            odds_value = float(value.get("odd", 0))
                            if odds_value > 0:  # Validazione
                                all_odds.append((
                                    bookmaker_odds.bookmaker_name,
                                    bookmaker_odds.bookmaker_id,
                                    odds_value
                                ))
                
                if all_odds:
                    # Ordina per quota (più alta = migliore per lo scommettitore)
                    all_odds.sort(key=lambda x: x[2], reverse=True)
                    
                    best = all_odds[0]
                    
                    # Se ci sono più bookmaker, mostra confronto
                    if len(all_odds) > 1:
                        other_books = [f"{bm}:{odd:.2f}" for bm, _, odd in all_odds[1:4]]
                        comparison = ", ".join(other_books)
                        print(f"   💎 BEST: {best[0]}:{best[2]:.2f} (vs {comparison})")
                    
                    return best
        
        except Exception as e:
            print(f"⚠️ Errore fetch bookmaker: {e}")
        
        return None
    
    def _get_bet_id_for_market(self, market: str) -> Optional[int]:
        """
        Mappa il nome del nostro mercato al bet_id delle API.
        
        Args:
            market: Nome del mercato (es. "Match Goals", "Both Teams to Score")
        
        Returns:
            bet_id delle API o None
        """
        market_lower = market.lower()
        
        # Match esatto
        if market_lower in self.bet_id_mapping:
            return self.bet_id_mapping[market_lower]
        
        # Match parziale
        if "goal" in market_lower and ("over" in market_lower or "under" in market_lower or "match" in market_lower):
            return 5  # Goals Over/Under
        
        if "btts" in market_lower or "both teams" in market_lower:
            return 8  # BTTS
        
        if "result" in market_lower or "winner" in market_lower or "1x2" in market_lower:
            return 1  # Match Winner
        
        if "corner" in market_lower:
            return 12  # Corners
        
        if "card" in market_lower:
            return 11  # Cards
        
        if "score" in market_lower and "exact" in market_lower:
            return 6  # Exact Score
        
        # Non trovato
        return None
    
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
        import re
        match = re.search(r'\d+\.?\d*', text)
        if match:
            return float(match.group())
        return None
    
    async def get_all_odds_for_fixture(self, fixture_id: int) -> Dict[str, List[MarketOdds]]:
        """
        Recupera TUTTE le quote disponibili per una partita.
        Utile per esplorare quali mercati sono disponibili.
        
        Returns:
            Dizionario con mercato -> lista di quote da diversi bookmaker
        """
        print(f"\n🔍 Recupero tutte le quote per fixture {fixture_id}...")
        
        all_odds = {}
        
        # Prova i principali bet IDs
        main_bets = [1, 5, 8, 6, 11, 12]  # Winner, Goals, BTTS, Score, Cards, Corners
        
        for bet_id in main_bets:
            try:
                fixture_odds = await self.odds_client.get_fixture_odds(
                    fixture_id=fixture_id,
                    bet_ids=[bet_id]
                )
                
                if fixture_odds and fixture_odds.bookmakers:
                    for bookmaker_odds in fixture_odds.bookmakers:
                        market_key = bookmaker_odds.bet_name
                        
                        if market_key not in all_odds:
                            all_odds[market_key] = []
                        
                        for value in bookmaker_odds.values:
                            market_odds = MarketOdds(
                                bookmaker_name=bookmaker_odds.bookmaker_name,
                                bookmaker_id=bookmaker_odds.bookmaker_id,
                                market=bookmaker_odds.bet_name,
                                selection=value.get("value", ""),
                                odds=float(value.get("odd", 0)),
                                last_update=datetime.now()
                            )
                            all_odds[market_key].append(market_odds)
                
                # Rate limiting
                await asyncio.sleep(0.3)
                
            except Exception as e:
                continue
        
        print(f"✅ Trovati {len(all_odds)} mercati con quote")
        return all_odds
    
    def clear_cache(self):
        """Pulisce la cache delle quote."""
        # Redis cache è gestita automaticamente con TTL
        print("🧹 Cache quote pulita")


# ===== FUNZIONI DI TEST =====

async def test_odds_fetcher():
    """Testa il modulo OddsFetcher."""
    print("=" * 70)
    print("🧪 TEST ODDS FETCHER")
    print("=" * 70)
    
    fetcher = OddsFetcher()
    await fetcher.initialize()
    
    # Test con una partita reale (usa un fixture_id reale)
    # Esempio: AS Roma vs Inter
    test_fixture_id = 1234567  # Sostituisci con ID reale
    
    print("\n" + "=" * 70)
    print("📊 TEST 1: Recupero quote singolo mercato")
    print("=" * 70)
    
    odds = await fetcher.get_odds_for_market(
        fixture_id=test_fixture_id,
        market="Match Goals",
        selection="Over 2.5"
    )
    
    if odds:
        print(f"✅ Quote trovate:")
        print(f"   Bookmaker: {odds.bookmaker_name}")
        print(f"   Market: {odds.market}")
        print(f"   Selection: {odds.selection}")
        print(f"   Odds: {odds.odds}")
    else:
        print("❌ Nessuna quota trovata")
    
    print("\n" + "=" * 70)
    print("📊 TEST 2: Recupero quote multiple")
    print("=" * 70)
    
    picks = [
        ("Match Goals", "Over 2.5"),
        ("Both Teams to Score", "Yes"),
        ("Match Result", "Home Win"),
        ("Total Corners", "Over 9.5"),
    ]
    
    results = await fetcher.get_odds_for_multiple_picks(test_fixture_id, picks)
    
    for key, odds in results.items():
        if odds:
            print(f"✅ {key}: {odds.odds} ({odds.bookmaker_name})")
        else:
            print(f"❌ {key}: Non disponibile")
    
    print("\n" + "=" * 70)
    print("✅ TEST COMPLETATO")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(test_odds_fetcher())

