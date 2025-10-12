"""
Player-specific betting predictions, focusing on cards and fouls.
"""

import asyncio
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

from core.models import TeamStats, Fixture
from adapters.football_api import FootballAPIClient
from adapters.odds_api import OddsAPIClient
# Removed dependency on player_history_db (file deleted during cleanup)


@dataclass
class PlayerStats:
    """Statistics for a player in the current season."""
    id: int
    name: str
    position: str
    team_id: int
    
    # Match statistics
    appearances: int = 0
    minutes_played: int = 0
    
    # Card statistics
    yellow_cards: int = 0
    red_cards: int = 0
    
    # Foul statistics
    fouls_committed: int = 0
    fouls_drawn: int = 0
    
    # Historical data for enhanced predictions
    # historical_data: List[PlayerHistoricalData] = None  # Removed - file deleted during cleanup
    
    # Calculated rates
    @property
    def yellow_cards_per_game(self) -> float:
        """Yellow cards per game."""
        return self.yellow_cards / self.appearances if self.appearances > 0 else 0.0
    
    @property
    def fouls_per_game(self) -> float:
        """Fouls committed per game."""
        return self.fouls_committed / self.appearances if self.appearances > 0 else 0.0
    
    @property
    def minutes_per_yellow(self) -> float:
        """Minutes played per yellow card."""
        return self.minutes_played / self.yellow_cards if self.yellow_cards > 0 else float('inf')
    
    @property
    def historical_card_rate(self) -> float:
        """Average card rate from historical data."""
        if not self.historical_data:
            return self.yellow_cards_per_game
        
        total_rate = 0.0
        total_weight = 0.0
        
        for i, hist in enumerate(self.historical_data):
            # More recent seasons have higher weight
            weight = 2.0 if i == 0 else 1.0
            total_rate += hist.yellow_cards_per_game * weight
            total_weight += weight
        
        return total_rate / total_weight if total_weight > 0 else self.yellow_cards_per_game
    
    @property
    def card_probability(self) -> float:
        """Enhanced probability using historical data (0-1)."""
        if self.appearances == 0 and not self.historical_data:
            return 0.0
        
        # Use historical rate if available, otherwise current season
        base_rate = self.historical_card_rate
        base_prob = min(base_rate, 1.0)
        
        # Adjust based on position (defenders and midfielders more likely)
        position_multiplier = {
            'defender': 1.2,
            'midfielder': 1.1,
            'forward': 0.9,
            'goalkeeper': 0.3
        }.get(self.position.lower(), 1.0)
        
        # Adjust based on foul rate
        foul_factor = min(self.fouls_per_game / 2.0, 0.3)  # Max 30% bonus
        
        # Historical consistency bonus
        consistency_bonus = 0.0
        if self.historical_data and len(self.historical_data) >= 2:
            rates = [h.yellow_cards_per_game for h in self.historical_data]
            if all(r > 0.2 for r in rates):  # Consistently gets cards
                consistency_bonus = 0.1
        
        return min(base_prob * position_multiplier + foul_factor + consistency_bonus, 0.95)


@dataclass
class PlayerCardPrediction:
    """Prediction for a player to receive a card."""
    player: PlayerStats
    match_fixture: Fixture
    
    # Prediction details
    probability: float  # 0-1
    confidence: str  # HIGH, MEDIUM, LOW
    reasoning: str
    
    # Market information
    market_name: str = "Player to be booked"
    market_id: int = 102  # API market ID
    
    # Odds information
    estimated_odds: str = ""
    real_odds: Optional[float] = None
    bookmaker: str = ""
    value_rating: str = ""
    
    @property
    def percentage(self) -> float:
        """Probability as percentage."""
        return self.probability * 100


@dataclass
class MatchPlayerPredictions:
    """All player predictions for a match."""
    fixture: Fixture
    home_predictions: List[PlayerCardPrediction]
    away_predictions: List[PlayerCardPrediction]
    
    @property
    def high_confidence_picks(self) -> List[PlayerCardPrediction]:
        """Get high confidence predictions."""
        all_predictions = self.home_predictions + self.away_predictions
        return [p for p in all_predictions if p.confidence == "HIGH"]
    
    @property
    def top_5_picks(self) -> List[PlayerCardPrediction]:
        """Get top 5 predictions by probability."""
        all_predictions = self.home_predictions + self.away_predictions
        return sorted(all_predictions, key=lambda x: x.probability, reverse=True)[:5]


class PlayerCardPredictor:
    """Predicts player card probabilities."""
    
    def __init__(self):
        self.api_client = FootballAPIClient()
        self.odds_client = OddsAPIClient()
        # self.history_db = PlayerHistoryDatabase()  # Removed - file deleted during cleanup
    
    async def analyze_match_players(self, fixture: Fixture, league_id: int, season: int) -> MatchPlayerPredictions:
        """Analyze players for card predictions in a match."""
        
        # Store current fixture for team name resolution
        self._current_fixture = fixture
        
        # Get squad information for both teams
        home_players = await self._get_team_players(fixture.home_team.id, league_id, season)
        away_players = await self._get_team_players(fixture.away_team.id, league_id, season)
        
        # Generate predictions
        home_predictions = self._generate_team_predictions(home_players, fixture, "home")
        away_predictions = self._generate_team_predictions(away_players, fixture, "away")
        
        return MatchPlayerPredictions(
            fixture=fixture,
            home_predictions=home_predictions,
            away_predictions=away_predictions
        )
    
    async def _get_team_players(self, team_id: int, league_id: int, season: int) -> List[PlayerStats]:
        """Get real player statistics for a team from API."""
        try:
            # Get current squad from API
            squad_data = await self.api_client.get_team_squad(team_id, season)
            
            if not squad_data:
                print(f"⚠️ No squad data found for team {team_id}, using fallback")
                return await self._get_fallback_players(team_id, season)
            
            players = []
            
            # Convert API data to PlayerStats objects
            for player_data in squad_data:
                if not player_data.get("name"):
                    continue
                
                # Get historical data for this player
                historical_data = self.history_db.get_player_history(player_data["name"], seasons=2)
                
                # Ensure minimum values for better predictions (handle None values)
                appearances = max(player_data.get("appearances") or 0, 1)
                yellow_cards = max(player_data.get("yellow_cards") or 0, 0)
                fouls_committed = max(player_data.get("fouls_committed") or 0, 0)
                red_cards = player_data.get("red_cards") or 0
                fouls_drawn = player_data.get("fouls_drawn") or 0
                minutes_played = max(player_data.get("minutes") or 0, appearances * 60)
                
                player = PlayerStats(
                    id=player_data.get("id", team_id * 1000 + len(players)),
                    name=player_data["name"],
                    position=self._normalize_position(player_data.get("position", "Midfielder")),
                    team_id=team_id,
                    appearances=appearances,
                    minutes_played=minutes_played,
                    yellow_cards=yellow_cards,
                    red_cards=red_cards,
                    fouls_committed=fouls_committed,
                    fouls_drawn=fouls_drawn,
                    historical_data=historical_data
                )
                
                players.append(player)
            
            # Filter out goalkeepers and sort by card propensity
            field_players = [p for p in players if p.position.lower() != "goalkeeper"]
            
            # Sort by a combination of cards and fouls to get the most likely to be booked
            def card_score(player):
                base_score = player.yellow_cards + (player.fouls_committed * 0.1)
                # Boost defenders and midfielders
                position_boost = {"defender": 1.2, "midfielder": 1.1, "forward": 0.9}.get(player.position.lower(), 1.0)
                # Historical boost
                hist_boost = 1.0
                if player.historical_data:
                    avg_hist_cards = sum(h.yellow_cards_per_game for h in player.historical_data) / len(player.historical_data)
                    hist_boost = 1 + (avg_hist_cards * 0.5)
                
                return base_score * position_boost * hist_boost
            
            field_players.sort(key=card_score, reverse=True)
            
            # Return top players most likely to get cards
            return field_players[:6]
            
        except Exception as e:
            print(f"⚠️ Error fetching real squad data: {e}")
            return await self._get_fallback_players(team_id, season)
    
    async def _get_fallback_players(self, team_id: int, season: int) -> List[PlayerStats]:
        """Fallback method using historical data when API fails."""
        # Get team name from fixture
        team_name = ""
        if hasattr(self, '_current_fixture'):
            if team_id == self._current_fixture.home_team.id:
                team_name = self._current_fixture.home_team.name
            else:
                team_name = self._current_fixture.away_team.name
        
        # Use historical top card players for this team
        historical_players = self.history_db.get_team_top_cards(team_name, season - 1, limit=6)
        
        players = []
        
        if historical_players:
            for i, hist_player in enumerate(historical_players):
                current_appearances = min(hist_player.appearances + 2, 20)
                historical_data = self.history_db.get_player_history(hist_player.player_name, seasons=2)
                
                player = PlayerStats(
                    id=team_id * 100 + i,
                    name=hist_player.player_name,
                    position=self._infer_position_from_name(hist_player.player_name),
                    team_id=team_id,
                    appearances=current_appearances,
                    minutes_played=current_appearances * 75,
                    yellow_cards=max(1, int(hist_player.yellow_cards_per_game * current_appearances)),
                    fouls_committed=max(5, int((hist_player.fouls_committed / hist_player.appearances) * current_appearances)),
                    historical_data=historical_data
                )
                players.append(player)
        
        # Fill with generic players if needed
        while len(players) < 3:
            pos = ["defender", "midfielder", "forward"][len(players)]
            base_stats = {
                "defender": {"yellow_cards": 3, "fouls": 22, "appearances": 15},
                "midfielder": {"yellow_cards": 2, "fouls": 16, "appearances": 14},
                "forward": {"yellow_cards": 1, "fouls": 8, "appearances": 12}
            }
            
            stats = base_stats[pos]
            player = PlayerStats(
                id=team_id * 100 + len(players),
                name=f"{team_name} {pos.title()} {len(players)+1}",
                position=pos,
                team_id=team_id,
                appearances=stats["appearances"],
                minutes_played=stats["appearances"] * 75,
                yellow_cards=stats["yellow_cards"],
                fouls_committed=stats["fouls"]
            )
            players.append(player)
        
        return players[:3]
    
    def _normalize_position(self, position: str) -> str:
        """Normalize position names from API."""
        if not position:
            return "midfielder"
        
        pos = position.lower()
        
        if any(word in pos for word in ['defender', 'defence', 'back']):
            return 'defender'
        elif any(word in pos for word in ['midfielder', 'midfield', 'mid']):
            return 'midfielder'
        elif any(word in pos for word in ['forward', 'attacker', 'striker', 'winger']):
            return 'forward'
        elif any(word in pos for word in ['goalkeeper', 'keeper', 'gk']):
            return 'goalkeeper'
        else:
            return 'midfielder'  # Default
    
    def _infer_position_from_name(self, player_name: str) -> str:
        """Infer position from player name (basic heuristic)."""
        name_lower = player_name.lower()
        
        # Known defenders
        if any(word in name_lower for word in ['mancini', 'bastoni', 'tomori', 'hernandez', 'di lorenzo', 'danilo']):
            return 'defender'
        
        # Known midfielders  
        if any(word in name_lower for word in ['pellegrini', 'barella', 'tonali', 'bennacer', 'lobotka', 'locatelli', 'rabiot']):
            return 'midfielder'
        
        # Known forwards
        if any(word in name_lower for word in ['chiesa', 'osimhen', 'lautaro', 'leao']):
            return 'forward'
        
        # Default based on typical patterns
        return 'midfielder'  # Most common position for card-prone players
    
    def _generate_team_predictions(self, players: List[PlayerStats], fixture: Fixture, team_side: str) -> List[PlayerCardPrediction]:
        """Generate card predictions for team players."""
        predictions = []
        
        for player in players:
            probability = player.card_probability
            
            # Determine confidence level
            if probability >= 0.4:
                confidence = "HIGH"
            elif probability >= 0.25:
                confidence = "MEDIUM"
            else:
                confidence = "LOW"
            
            # Generate reasoning
            reasoning = self._generate_player_reasoning(player, team_side)
            
            # Estimate odds (inverse of probability with bookmaker margin)
            if probability > 0:
                estimated_decimal_odds = (1 / probability) * 1.1  # 10% margin
                estimated_odds = f"{estimated_decimal_odds:.2f}"
            else:
                estimated_odds = "N/A"
            
            prediction = PlayerCardPrediction(
                player=player,
                match_fixture=fixture,
                probability=probability,
                confidence=confidence,
                reasoning=reasoning,
                estimated_odds=estimated_odds
            )
            
            predictions.append(prediction)
        
        # Sort by probability (highest first)
        return sorted(predictions, key=lambda x: x.probability, reverse=True)
    
    def _generate_player_reasoning(self, player: PlayerStats, team_side: str) -> str:
        """Generate reasoning for player card prediction with historical context."""
        reasons = []
        
        # Position-based reasoning
        position_reasons = {
            'defender': f"Difensore con ruolo di contrasto",
            'midfielder': f"Centrocampista con compiti di interdizione",
            'forward': f"Attaccante, meno esposto ai cartellini",
            'goalkeeper': f"Portiere, raramente ammonito"
        }
        reasons.append(position_reasons.get(player.position.lower(), "Posizione non specificata"))
        
        # Historical context
        if player.historical_data:
            hist_rate = player.historical_card_rate
            if hist_rate > 0.3:
                reasons.append(f"Storico: alto rischio ({hist_rate:.1f} cartellini/partita)")
            elif hist_rate > 0.15:
                reasons.append(f"Storico: rischio moderato ({hist_rate:.1f} cartellini/partita)")
            else:
                reasons.append(f"Storico: basso rischio ({hist_rate:.1f} cartellini/partita)")
            
            # Consistency check
            if len(player.historical_data) >= 2:
                rates = [h.yellow_cards_per_game for h in player.historical_data]
                if all(r > 0.2 for r in rates):
                    reasons.append("Costantemente ammonito nelle ultime stagioni")
                elif any(r > 0.4 for r in rates):
                    reasons.append("Ha avuto stagioni con molti cartellini")
        
        # Current season statistics
        current_rate = player.yellow_cards_per_game
        if current_rate > 0.3:
            reasons.append(f"Stagione corrente: {current_rate:.1f} cartellini/partita")
        
        if player.fouls_per_game > 2.0:
            reasons.append(f"Molti falli: {player.fouls_per_game:.1f}/partita")
        elif player.fouls_per_game > 1.0:
            reasons.append(f"Falli nella media: {player.fouls_per_game:.1f}/partita")
        
        # Playing time consideration
        if player.appearances >= 15:
            reasons.append(f"Titolare fisso ({player.appearances} presenze)")
        elif player.appearances >= 8:
            reasons.append(f"Rotazione ({player.appearances} presenze)")
        else:
            reasons.append(f"Poco utilizzato ({player.appearances} presenze)")
        
        return " | ".join(reasons)
    
    async def enhance_with_real_odds(self, predictions: MatchPlayerPredictions) -> MatchPlayerPredictions:
        """Enhance predictions with real odds from bookmakers."""
        # For now, return as-is since player odds require more complex API integration
        # TODO: Implement real odds fetching for player markets
        return predictions
