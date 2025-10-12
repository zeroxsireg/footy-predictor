"""Main daily league analyzer orchestrator."""

import asyncio
from typing import List, Dict, Optional
from datetime import datetime

from .daily_models import DailyPick, DailyLeagueAnalysis, BettingCombination
from .pick_selector import PickSelector
from .models import Fixture, MatchPrediction
from .analyzer import MatchAnalyzer
from betting.orchestrator import BettingOrchestrator
from analyzers.player_cards_analyzer import PlayerCardsAnalyzer  # NUOVO MODULO
from .betting_models import BettingRecommendation
from .config import get_settings
from adapters.football_api import FootballAPIClient
from .odds_fetcher import OddsFetcher  # MODULO QUOTE BOOKMAKER


class DailyLeagueAnalyzer:
    """Main orchestrator for daily league analysis."""
    
    def __init__(self):
        self.settings = get_settings()
        self.match_analyzer = MatchAnalyzer()
        self.betting_orchestrator = BettingOrchestrator()
        self.pick_selector = PickSelector()
        self.player_card_analyzer = PlayerCardsAnalyzer()  # NUOVO MODULO
        self.api_client = FootballAPIClient()
        self.odds_fetcher = OddsFetcher()  # MODULO QUOTE BOOKMAKER
        self._odds_initialized = False  # Flag per inizializzazione una tantum

    async def analyze_league_matchday(
        self, 
        country: str, 
        league_name: str, 
        country_flag: str, 
        country_it: str, 
        season: Optional[int] = None,
        specific_fixtures: Optional[List] = None,
        target_date: Optional[datetime] = None,
        return_all_recommendations: bool = False
    ) -> DailyLeagueAnalysis:
        """Analyze all matches of the next matchday for a league."""
        
        print(f"\n⚽ ANALISI GIORNATA COMPLETA - {league_name}")
        print("=" * 60)
        
        # Get league fixtures
        league_id = await self.api_client.get_league_id(country, league_name, season or 2025)
        
        if target_date:
            # For specific date analysis (cross-league)
            fixtures = await self._get_fixtures_for_date(league_id, season or 2025, target_date)
            matchday = f"Specific Date ({target_date.strftime('%d/%m/%Y')})"
        elif specific_fixtures:
            # Legacy support for specific fixtures
            fixtures = specific_fixtures
            matchday = "Specific Date"
        else:
            # Normal analysis (next matchday)
            fixtures, matchday = await self.api_client.get_next_round_fixtures(league_id, season or 2025, country)
        
        if not fixtures:
            raise ValueError(f"Nessuna partita trovata per {league_name}")
        
        print(f"📅 Giornata {matchday} - {len(fixtures)} partite da analizzare")
        
        # Cache standings ONCE for the entire analysis
        print("📊 Fetching league standings...")
        standings = await self._get_league_standings(league_id)
        if standings:
            print(f"✅ Cached standings for {len(standings)} teams")
        else:
            print("⚠️ Could not fetch standings, proceeding without ranking context")
        
        print("⏳ Analisi in corso...")
        all_picks = []
        all_player_cards_picks = []  # Collect all individual player card picks
        analyzable_matches = 0
        
        for i, fixture in enumerate(fixtures, 1):
            try:
                print(f"  🔍 [{i}/{len(fixtures)}] {fixture.home_team.name} vs {fixture.away_team.name}")
                
                # Analyze single match
                prediction = await self.match_analyzer._analyze_single_match(
                    fixture, league_id, season or 2025
                )
                
                if prediction.status == "TO AVOID":
                    print(f"⚠️ Match {fixture.home_team.name} vs {fixture.away_team.name} marked as TO AVOID (untracked teams: {', '.join(prediction.untracked_teams)})")
                    continue
                
                betting_analysis = self.betting_orchestrator.analyze_match(
                    prediction.home_stats, prediction.away_stats
                )
                
                # Convert to DailyPicks - Select the BEST pick per match with market diversity
                if betting_analysis.recommendations:
                    if return_all_recommendations:
                        # For cross-league analysis: collect ALL recommendations from ALL matches
                        for rec in betting_analysis.recommendations:
                            pick = DailyPick(
                                match_id=fixture.id,
                                home_team=fixture.home_team.name,
                                away_team=fixture.away_team.name,
                                market=rec.market,
                                selection=rec.selection,
                                confidence=rec.confidence,
                                percentage=rec.percentage,
                                reasoning=rec.reasoning,
                                match_time=fixture.date,
                                league=league_name,
                                real_odds=None,
                                bookmaker=None
                            )
                            all_picks.append(pick)
                    else:
                        # NUOVA STRATEGIA: 5 PICKS PER PARTITA (50 TOTALI)
                        # - 2 picks OBBLIGATORI da Goals/BTTS (sempre presenti)
                        # - 3 picks MIGLIORI da Shots/Corners/Cards/Result
                        
                        all_recs = sorted(betting_analysis.recommendations, key=lambda x: x.percentage, reverse=True)
                        
                        # Separa per categoria
                        goals_btts_picks = [r for r in all_recs if self._get_market_category(r.market) in ["Goals", "BTTS"]]
                        other_picks = [r for r in all_recs if self._get_market_category(r.market) not in ["Goals", "BTTS"]]
                        
                        selected_picks = []
                        markets_used = []
                        
                        # PICKS 1-2: I 2 MIGLIORI da Goals/BTTS (OBBLIGATORI)
                        for rec in goals_btts_picks[:2]:  # Top 2 da Goals/BTTS
                            base_market = self._normalize_market_name(rec.market)
                            if base_market not in markets_used:
                                selected_picks.append(rec)
                                markets_used.append(base_market)
                        
                        # PICKS 3-5: I 3 MIGLIORI dagli altri mercati (Shots, Corners, Cards, Result)
                        for rec in other_picks:
                            if len(selected_picks) >= 5:
                                break
                            base_market = self._normalize_market_name(rec.market)
                            if base_market not in markets_used:
                                selected_picks.append(rec)
                                markets_used.append(base_market)
                        
                        # Fallback: Se Goals/BTTS non ha generato 2 picks, riempi con altri
                        if len(selected_picks) < 5:
                            for rec in all_recs:
                                if len(selected_picks) >= 5:
                                    break
                                base_market = self._normalize_market_name(rec.market)
                                if base_market not in markets_used:
                                    selected_picks.append(rec)
                                    markets_used.append(base_market)
                        
                        # Aggiungi i picks selezionati
                        for i, rec in enumerate(selected_picks, 1):
                            confidence_label = "High" if rec.percentage >= 75 else "Medium" if rec.percentage >= 60 else "Low"
                            category = self._get_market_category(rec.market)
                            print(f"    💰 Pick {i} ({category}, {rec.percentage:.0f}%): {rec.market} - {rec.selection}")
                            
                            pick = DailyPick(
                                match_id=fixture.id,
                                home_team=fixture.home_team.name,
                                away_team=fixture.away_team.name,
                                market=rec.market,
                                selection=rec.selection,
                                confidence=rec.confidence,
                                percentage=rec.percentage,
                                reasoning=rec.reasoning,
                                match_time=fixture.date,
                                league=league_name,
                                real_odds=None,
                                bookmaker=None
                            )
                            all_picks.append(pick)
                    
                    # Generate individual player cards predictions for this match (NUOVO MODULO)
                    player_cards_picks = await self.player_card_analyzer.analyze_match_players(
                        fixture, standings, league_name, self.api_client
                    )
                    all_player_cards_picks.extend(player_cards_picks)  # Add to global collection
                
                analyzable_matches += 1
                await asyncio.sleep(0.5) # Small delay to prevent overwhelming the system
                
            except Exception as e:
                print(f"❌ Errore durante l'analisi della partita {fixture.home_team.name} vs {fixture.away_team.name}: {e}")
                continue
        
        # Generate top picks (prima delle quote)
        top_picks = self.pick_selector._rank_picks(all_picks)
        
        print(f"\n✅ Analisi completata: {analyzable_matches}/{len(fixtures)} partite analizzabili")
        
        # ===== ENRICHMENT CON QUOTE REALI (PRIMA DI CALCOLARE LE COMBINAZIONI) =====
        await self._enrich_picks_with_odds(top_picks, fixtures)
        
        # Generate combinations DOPO aver fetchato le quote reali
        combinations = self.pick_selector._generate_combinations(top_picks)
        
        # Create summary
        summary = self.pick_selector._create_summary(all_picks, top_picks, combinations)
        
        # Sort player cards picks by probability and get top 8
        top_8_player_cards = sorted(all_player_cards_picks, key=lambda p: p.percentage, reverse=True)[:8]
        
        return DailyLeagueAnalysis(
            league_name=league_name,
            country_flag=country_flag,
            round_number=matchday if isinstance(matchday, int) else 1,
            total_matches_analyzed=analyzable_matches,
            total_picks_generated=len(all_picks),
            analysis_timestamp=datetime.now(),
            top_picks=top_picks,
            optimal_combinations=combinations,
            summary_stats=summary,
            best_category_picks={},  # Will be filled by display module
            recommended_strategy="Mix di singoli picks + combinazioni",
            top_player_cards_picks=top_8_player_cards  # Add player cards picks
        )
    

    async def _get_fixtures_for_date(self, league_id: int, season: int, target_date: datetime) -> List:
        """Get fixtures for a specific date and league."""
        try:
            params = {
                "league": league_id,
                "season": season,
                "date": target_date.strftime('%Y-%m-%d')
            }
            
            data = await self.api_client._make_request("/fixtures", params)
            
            if not data.get("response"):
                return []
            
            fixtures = []
            for fixture_data in data["response"]:
                fixture = self.api_client._parse_fixture(fixture_data, "Unknown")
                fixtures.append(fixture)
            
            return fixtures
            
        except Exception as e:
            print(f"   ⚠️ Errore nel recupero partite per league {league_id}: {e}")
            return []

    async def _get_league_standings(self, league_id: int) -> Optional[List[Dict]]:
        """Get league standings from API."""
        try:
            return await self.api_client.get_league_standings(league_id, self.settings.default_season)
        except Exception as e:
            print(f"⚠️ Could not fetch league standings: {e}")
            return None

    def _get_market_category(self, market: str) -> str:
        """Determina categoria principale del mercato."""
        if "Match Goals" in market or "Over" in market or "Under" in market:
            return "Goals"
        elif "Both Teams to Score" in market or "BTTS" in market:
            return "BTTS"
        elif "Match Result" in market or "(Home Win)" in market or "(Draw)" in market or "(Away Win)" in market:
            return "Result"
        elif "Shots" in market:
            return "Shots"
        elif "Corners" in market:
            return "Corners"
        elif "Cards" in market:
            return "Cards"
        else:
            return "Other"
    
    def _normalize_market_name(self, market: str) -> str:
        """
        Normalizza il nome del mercato per evitare duplicati.
        Es: "Total Shots: Over 16.5" → "Total Shots"
            "AS Roma Shots: Over 10.5" → "AS Roma Shots"
            "Match Goals: Over 1.5" → "Match Goals"
        """
        # Rimuove ": Over/Under X.X" dal mercato
        if ": Over" in market or ": Under" in market:
            return market.split(":")[0].strip()
        return market
    
    def _enhance_cards_with_ranking_context(self, recommendation: BettingRecommendation, 
                                          fixture, standings: List[Dict]) -> BettingRecommendation:
        """Enhance cards recommendation with ranking context."""
        # Ranking context enhancement rimosso - non necessario con nuovo modulo
        # Il nuovo PlayerCardsAnalyzer già considera il contesto nella sua logica
        return recommendation

    def _get_ranking_context_description(self, home_position: int, away_position: int) -> str:
        """Get description of ranking context."""
        position_diff = abs(home_position - away_position)
        
        if position_diff >= 8:
            return "Grande differenza di qualità"
        elif position_diff >= 5:
            return "Notevole differenza in classifica"
        elif position_diff >= 3:
            return "Moderata differenza in classifica"
        elif position_diff <= 2:
            return "Squadre di livello simile"
        else:
            return ""
    
    async def _enrich_picks_with_odds(self, picks: List[DailyPick], fixtures: List) -> None:
        """
        Arricchisce i picks con le quote reali dai bookmaker.
        Modifica i picks in-place aggiungendo bookmaker e real_odds.
        """
        if not picks:
            return
        
        # Inizializza l'odds fetcher (solo la prima volta, silent mode)
        if not self._odds_initialized:
            success = await self.odds_fetcher.initialize()
            self._odds_initialized = True
            
            if not success:
                return
        
        # Crea mapping fixture_id per ogni partita
        fixture_map = {}
        for fixture in fixtures:
            match_key = f"{fixture.home_team.name} vs {fixture.away_team.name}"
            fixture_map[match_key] = fixture.id
        
        print(f"\n💰 Recupero quote reali per {len(picks)} picks da bookmaker...")
        print("=" * 70)
        
        success_count = 0
        failed_markets = set()
        
        # Processa i picks in batch per efficienza
        for pick in picks:
            match_key = f"{pick.home_team} vs {pick.away_team}"
            fixture_id = fixture_map.get(match_key)
            
            if not fixture_id:
                continue
            
            try:
                # Recupera quote per questo pick
                odds_info = await self.odds_fetcher.get_odds_for_market(
                    fixture_id=fixture_id,
                    market=pick.market,
                    selection=pick.selection
                )
                
                if odds_info:
                    # Arricchisci il pick con le quote reali
                    pick.bookmaker = odds_info.bookmaker_name
                    pick.real_odds = odds_info.odds
                    success_count += 1
                    
                    print(f"✅ {pick.market}: {pick.selection} → {odds_info.odds:.2f} ({odds_info.bookmaker_name})")
                else:
                    failed_markets.add(pick.market)
                
            except Exception as e:
                print(f"⚠️ Errore recupero quote per {pick.market}: {e}")
                continue
        
        print("=" * 70)
        print(f"📊 RIEPILOGO QUOTE:")
        print(f"   ✅ Quote trovate: {success_count}/{len(picks)}")
        print(f"   ❌ Quote mancanti: {len(picks) - success_count}/{len(picks)}")
        
        if failed_markets:
            print(f"\n⚠️ Mercati senza quote disponibili (non supportati dai bookmaker):")
            for market in sorted(failed_markets):
                print(f"   • {market}")
            print(f"\n💡 NOTA: Shots, Shots on Goal e mercati team-specific non sono")
            print(f"   disponibili nelle API dei bookmaker. Solo Goals, BTTS, Result,")
            print(f"   Corners e Cards hanno quote reali.")
        
        print("=" * 70)
