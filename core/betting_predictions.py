"""Betting predictions based on team statistics."""

from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional, Any
from .models import TeamStats, MatchPrediction
from .player_predictions import PlayerCardPredictor, MatchPlayerPredictions


@dataclass
class BettingRecommendation:
    """A single betting recommendation."""
    market: str
    selection: str
    confidence: str  # "HIGH", "MEDIUM", "LOW"
    odds_range: str  # Estimated odds range
    reasoning: str
    percentage: float  # Probability percentage
    real_odds: Optional[float] = None  # Real odds from bookmakers
    bookmaker: Optional[str] = None  # Bookmaker name
    value_rating: Optional[str] = None  # "EXCELLENT", "GOOD", "FAIR", "POOR"


@dataclass
class ExactScorePrediction:
    """Exact score prediction."""
    score: str  # e.g., "1-0"
    probability: float
    reasoning: str
    odds_estimate: str


@dataclass
class MatchBettingAnalysis:
    """Complete betting analysis for a match."""
    match_info: str
    recommendations: List[BettingRecommendation]
    exact_scores: List[ExactScorePrediction]
    summary: Dict[str, str]
    player_predictions: Optional[MatchPlayerPredictions] = None


class BettingPredictor:
    """Generates betting predictions from team statistics."""
    
    def __init__(self):
        # Confidence thresholds
        self.HIGH_CONFIDENCE = 70.0
        self.MEDIUM_CONFIDENCE = 60.0
        self.player_predictor = PlayerCardPredictor()
    
    async def analyze_match(self, prediction: MatchPrediction, league_id: int = None, season: int = None) -> MatchBettingAnalysis:
        """Generate complete betting analysis for a match."""
        home_stats = prediction.home_stats
        away_stats = prediction.away_stats
        
        recommendations = []
        
        # Under/Over Goals Analysis
        recommendations.extend(self._analyze_under_over_goals(home_stats, away_stats))
        
        # BTTS Analysis
        recommendations.extend(self._analyze_btts(home_stats, away_stats))
        
        # Shots Analysis
        recommendations.extend(self._analyze_shots(home_stats, away_stats))
        
        # Corners Analysis
        recommendations.extend(self._analyze_corners(home_stats, away_stats))
        
        # Cards Analysis
        recommendations.extend(self._analyze_cards(home_stats, away_stats))
        
        # Exact Score Predictions
        exact_scores = self._predict_exact_scores(home_stats, away_stats)
        
        # Generate player predictions using real API data
        if league_id and season:
            player_predictions = await self.player_predictor.analyze_match_players(
                prediction.fixture, 
                league_id, 
                season
            )
        else:
            # Fallback to sync version with historical data
            player_predictions = self._generate_player_predictions_sync(prediction)
        
        # Create summary
        summary = self._create_summary(recommendations)
        
        match_info = f"{home_stats.team.name} vs {away_stats.team.name}"
        
        return MatchBettingAnalysis(
            match_info=match_info,
            recommendations=recommendations,
            exact_scores=exact_scores,
            summary=summary,
            player_predictions=player_predictions
        )
    
    def _generate_betting_analysis_sync(self, prediction: MatchPrediction) -> MatchBettingAnalysis:
        """Generate betting analysis synchronously using historical data only."""
        home_stats = prediction.home_stats
        away_stats = prediction.away_stats
        
        recommendations = []
        
        # Under/Over Analysis
        recommendations.extend(self._analyze_under_over_goals(home_stats, away_stats))
        
        # BTTS Analysis
        recommendations.extend(self._analyze_btts(home_stats, away_stats))
        
        # Shots Analysis
        recommendations.extend(self._analyze_shots(home_stats, away_stats))
        
        # Corners Analysis
        recommendations.extend(self._analyze_corners(home_stats, away_stats))
        
        # Cards Analysis
        recommendations.extend(self._analyze_cards(home_stats, away_stats))
        
        # Exact Score Predictions
        exact_scores = self._predict_exact_scores(home_stats, away_stats)
        
        # Generate player predictions (synchronous version using historical data only)
        player_predictions = self._generate_player_predictions_sync(prediction)
        
        # Create summary
        summary = self._create_summary(recommendations)
        
        match_info = f"{home_stats.team.name} vs {away_stats.team.name}"
        
        return MatchBettingAnalysis(
            match_info=match_info,
            recommendations=recommendations,
            exact_scores=exact_scores,
            summary=summary,
            player_predictions=player_predictions
        )
    
    async def enhance_with_real_odds(self, analysis: MatchBettingAnalysis, fixture_id: int) -> MatchBettingAnalysis:
        """Enhance betting analysis with real odds from bookmakers."""
        try:
            from adapters.odds_api import OddsAPIClient
            from core.config import get_settings
            
            settings = get_settings()
            odds_client = OddsAPIClient()
            
            # Use preferred bookmakers from configuration
            popular_odds = await odds_client.get_popular_odds_for_fixture(
                fixture_id, 
                preferred_bookmakers=settings.preferred_bookmakers
            )
            
            # Enhance recommendations with real odds
            enhanced_recommendations = []
            for rec in analysis.recommendations:
                enhanced_rec = self._add_real_odds_to_recommendation(rec, popular_odds)
                enhanced_recommendations.append(enhanced_rec)
            
            # Update analysis
            analysis.recommendations = enhanced_recommendations
            
            return analysis
            
        except Exception as e:
            print(f"⚠️ Could not fetch real odds: {e}")
            return analysis
    
    async def add_player_predictions(self, analysis: MatchBettingAnalysis, prediction: MatchPrediction, league_id: int, season: int) -> MatchBettingAnalysis:
        """Add player card predictions to the analysis."""
        try:
            player_predictions = await self.player_predictor.analyze_match_players(
                prediction.fixture, league_id, season
            )
            
            # Update the analysis with player predictions
            analysis.player_predictions = player_predictions
            return analysis
            
        except Exception as e:
            print(f"⚠️ Error generating player predictions: {e}")
            return analysis
    
    def _generate_player_predictions_sync(self, prediction: MatchPrediction) -> Optional[MatchPlayerPredictions]:
        """Generate player predictions synchronously using historical data."""
        try:
            # Create a simplified version without async API calls
            predictor = self.player_predictor
            fixture = prediction.fixture
            
            # Store fixture for team name resolution
            predictor._current_fixture = fixture
            
            # Get historical players for both teams
            home_players = self._get_team_players_sync(fixture.home_team.name, 2025)
            away_players = self._get_team_players_sync(fixture.away_team.name, 2025)
            
            # Generate predictions
            home_predictions = predictor._generate_team_predictions(home_players, fixture, "home")
            away_predictions = predictor._generate_team_predictions(away_players, fixture, "away")
            
            return MatchPlayerPredictions(
                fixture=fixture,
                home_predictions=home_predictions,
                away_predictions=away_predictions
            )
            
        except Exception as e:
            print(f"⚠️ Error in sync player predictions: {e}")
            return None
    
    def _get_team_players_sync(self, team_name: str, season: int) -> List:
        """Get team players synchronously using historical data."""
        from core.player_predictions import PlayerStats
        
        # Get historical top card players for this team
        historical_players = self.player_predictor.history_db.get_team_top_cards(team_name, season - 1, limit=6)
        
        players = []
        
        if historical_players:
            # Use historical data for known players
            for i, hist_player in enumerate(historical_players):
                # Simulate current season stats based on historical performance
                current_appearances = min(hist_player.appearances + 2, 20)  # Slightly more games
                historical_data = self.player_predictor.history_db.get_player_history(hist_player.player_name, seasons=2)
                
                player = PlayerStats(
                    id=i + 1000,
                    name=hist_player.player_name,
                    position=self._infer_position_from_name(hist_player.player_name),
                    team_id=i + 1000,
                    appearances=current_appearances,
                    minutes_played=current_appearances * 75,  # Assume ~75 min per game
                    yellow_cards=max(1, int(hist_player.yellow_cards_per_game * current_appearances)),
                    fouls_committed=max(5, int((hist_player.fouls_committed / hist_player.appearances) * current_appearances)),
                    historical_data=historical_data
                )
                players.append(player)
        
        # Fill remaining slots with generic players if needed
        while len(players) < 3:  # Top 3 players per team
            position_cycle = ["defender", "midfielder", "forward"]
            pos = position_cycle[len(players)]
            
            # Base stats by position
            base_stats = {
                "defender": {"yellow_cards": 3, "fouls": 22, "appearances": 15},
                "midfielder": {"yellow_cards": 2, "fouls": 16, "appearances": 14},
                "forward": {"yellow_cards": 1, "fouls": 8, "appearances": 12}
            }
            
            stats = base_stats[pos]
            player = PlayerStats(
                id=len(players) + 1000,
                name=f"{team_name} {pos.title()} {len(players)+1}",
                position=pos,
                team_id=len(players) + 1000,
                appearances=stats["appearances"],
                minutes_played=stats["appearances"] * 75,
                yellow_cards=stats["yellow_cards"],
                fouls_committed=stats["fouls"]
            )
            players.append(player)
        
        return players[:3]  # Return top 3 players
    
    def _infer_position_from_name(self, player_name: str) -> str:
        """Infer position from player name (basic heuristic)."""
        name_lower = player_name.lower()
        
        # Known defenders
        if any(word in name_lower for word in ['mancini', 'bastoni', 'tomori', 'hernandez', 'di lorenzo', 'danilo', 'ndicka', 'angelino', 'dumfries', 'acerbi', 'gabbia', 'rrahmani', 'olivera', 'cambiaso', 'kalulu', 'van dijk', 'hummels', 'gimenez', 'marquinhos']):
            return 'defender'
        
        # Known midfielders  
        if any(word in name_lower for word in ['pellegrini', 'barella', 'bennacer', 'lobotka', 'locatelli', 'cristante', 'paredes', 'anguissa', 'reijnders', 'musah', 'loftus-cheek', 'calhanoglu', 'mkhitaryan', 'mckennie', 'thuram', 'mctominay', 'fernandes', 'casemiro', 'rice', 'rodri', 'gallagher', 'kimmich', 'goretzka', 'xhaka', 'pedri', 'gavi', 'modric', 'koke', 'verratti', 'fofana', 'andre']):
            return 'midfielder'
        
        # Known forwards
        if any(word in name_lower for word in ['leao', 'osimhen', 'lautaro']):
            return 'forward'
        
        # Default based on typical patterns
        return 'midfielder'  # Most common position for card-prone players
    
    def _add_real_odds_to_recommendation(self, rec: BettingRecommendation, 
                                       popular_odds: Dict[str, Any]) -> BettingRecommendation:
        """Add real odds to a recommendation if available."""
        # Map our recommendations to API markets
        market_mapping = {
            "Match Goals": "over_under_25",
            "Both Teams to Score": "both_teams_score",
            "Total Shots": None,  # Not available in odds API
            "Total Corners": None,  # Not available in odds API
            "Total Cards": None,  # Not available in odds API
        }
        
        api_market = market_mapping.get(rec.market)
        if not api_market or api_market not in popular_odds or not popular_odds[api_market]:
            return rec
        
        bookmaker_odds = popular_odds[api_market]
        
        # Find matching selection in odds
        real_odds = None
        bookmaker_name = bookmaker_odds.bookmaker_name
        
        for value in bookmaker_odds.values:
            selection_text = value.get("value", "").lower()
            rec_selection = rec.selection.lower()
            
            # Match selections
            if ("over" in rec_selection and "over" in selection_text) or \
               ("under" in rec_selection and "under" in selection_text) or \
               ("yes" in rec_selection and "yes" in selection_text) or \
               ("no" in rec_selection and "no" in selection_text):
                real_odds = float(value.get("odd", 0))
                break
        
        if real_odds:
            # Calculate value rating
            implied_prob = 100 / real_odds
            our_prob = rec.percentage
            
            if our_prob > implied_prob + 10:
                value_rating = "EXCELLENT"
            elif our_prob > implied_prob + 5:
                value_rating = "GOOD"
            elif our_prob > implied_prob:
                value_rating = "FAIR"
            else:
                value_rating = "POOR"
            
            # Update recommendation
            rec.real_odds = real_odds
            rec.bookmaker = bookmaker_name
            rec.value_rating = value_rating
        
        return rec
    
    def _analyze_under_over_goals(self, home_stats: TeamStats, away_stats: TeamStats) -> List[BettingRecommendation]:
        """Analyze Under/Over goals markets."""
        recommendations = []
        
        # Calculate combined percentages for match totals
        home_over_15 = home_stats.over_1_5_goals_percentage
        away_over_15 = away_stats.over_1_5_goals_percentage
        home_over_25 = home_stats.over_2_5_goals_percentage
        away_over_25 = away_stats.over_2_5_goals_percentage
        home_over_35 = home_stats.over_3_5_goals_percentage
        away_over_35 = away_stats.over_3_5_goals_percentage
        
        # Match Over/Under 1.5 Goals
        match_over_15_prob = (home_over_15 + away_over_15) / 2
        if match_over_15_prob >= self.HIGH_CONFIDENCE:
            recommendations.append(BettingRecommendation(
                market="Match Goals",
                selection="Over 1.5",
                confidence="HIGH",
                odds_range="1.20-1.40",
                reasoning=f"Both teams score 1.5+ goals in {match_over_15_prob:.1f}% of matches",
                percentage=match_over_15_prob
            ))
        elif match_over_15_prob <= 30:
            recommendations.append(BettingRecommendation(
                market="Match Goals",
                selection="Under 1.5",
                confidence="MEDIUM",
                odds_range="2.50-3.50",
                reasoning=f"Low scoring match expected ({match_over_15_prob:.1f}% over 1.5)",
                percentage=100 - match_over_15_prob
            ))
        
        # Match Over/Under 2.5 Goals
        match_over_25_prob = (home_over_25 + away_over_25) / 2
        if match_over_25_prob >= self.HIGH_CONFIDENCE:
            recommendations.append(BettingRecommendation(
                market="Match Goals",
                selection="Over 2.5",
                confidence="HIGH",
                odds_range="1.60-2.00",
                reasoning=f"High-scoring teams: {match_over_25_prob:.1f}% over 2.5 goals",
                percentage=match_over_25_prob
            ))
        elif match_over_25_prob <= 25:
            recommendations.append(BettingRecommendation(
                market="Match Goals",
                selection="Under 2.5",
                confidence="HIGH",
                odds_range="1.40-1.80",
                reasoning=f"Low-scoring match: {match_over_25_prob:.1f}% over 2.5 goals",
                percentage=100 - match_over_25_prob
            ))
        
        # Individual team Over/Under 1.5 Goals
        if home_over_15 >= self.HIGH_CONFIDENCE:
            recommendations.append(BettingRecommendation(
                market=f"{home_stats.team.name} Goals",
                selection="Over 1.5",
                confidence="HIGH",
                odds_range="1.80-2.50",
                reasoning=f"{home_stats.team.name} scores 1.5+ in {home_over_15:.1f}% of matches",
                percentage=home_over_15
            ))
        
        if away_over_15 >= self.HIGH_CONFIDENCE:
            recommendations.append(BettingRecommendation(
                market=f"{away_stats.team.name} Goals",
                selection="Over 1.5",
                confidence="HIGH",
                odds_range="1.80-2.50",
                reasoning=f"{away_stats.team.name} scores 1.5+ in {away_over_15:.1f}% of matches",
                percentage=away_over_15
            ))
        
        return recommendations
    
    def _analyze_btts(self, home_stats: TeamStats, away_stats: TeamStats) -> List[BettingRecommendation]:
        """Analyze Both Teams to Score market."""
        recommendations = []
        
        # BTTS probability = (1 - home_failed_to_score) * (1 - away_failed_to_score)
        home_score_prob = 100 - home_stats.failed_to_score_percentage
        away_score_prob = 100 - away_stats.failed_to_score_percentage
        
        btts_prob = (home_score_prob * away_score_prob) / 100
        
        if btts_prob >= self.HIGH_CONFIDENCE:
            recommendations.append(BettingRecommendation(
                market="Both Teams to Score",
                selection="YES",
                confidence="HIGH",
                odds_range="1.50-2.00",
                reasoning=f"Both teams score regularly ({home_score_prob:.1f}% vs {away_score_prob:.1f}%)",
                percentage=btts_prob
            ))
        elif btts_prob <= 40:
            recommendations.append(BettingRecommendation(
                market="Both Teams to Score",
                selection="NO",
                confidence="MEDIUM",
                odds_range="1.80-2.50",
                reasoning=f"One team likely to blank ({btts_prob:.1f}% BTTS probability)",
                percentage=100 - btts_prob
            ))
        
        return recommendations
    
    def _analyze_shots(self, home_stats: TeamStats, away_stats: TeamStats) -> List[BettingRecommendation]:
        """Analyze shots markets."""
        recommendations = []
        
        home_shots_avg = home_stats.shots_per_game
        away_shots_avg = away_stats.shots_per_game
        total_shots_expected = home_shots_avg + away_shots_avg
        
        # Total Shots Over/Under
        if total_shots_expected >= 25:
            recommendations.append(BettingRecommendation(
                market="Total Shots",
                selection="Over 24.5",
                confidence="HIGH",
                odds_range="1.70-2.20",
                reasoning=f"High shot volume expected: {total_shots_expected:.1f} shots/match",
                percentage=75.0
            ))
        elif total_shots_expected <= 18:
            recommendations.append(BettingRecommendation(
                market="Total Shots",
                selection="Under 20.5",
                confidence="MEDIUM",
                odds_range="1.60-2.00",
                reasoning=f"Low shot volume expected: {total_shots_expected:.1f} shots/match",
                percentage=65.0
            ))
        
        # Individual team shots
        if home_shots_avg >= 15:
            recommendations.append(BettingRecommendation(
                market=f"{home_stats.team.name} Shots",
                selection="Over 13.5",
                confidence="MEDIUM",
                odds_range="1.80-2.30",
                reasoning=f"{home_stats.team.name}: {home_shots_avg:.1f} shots/match average",
                percentage=65.0
            ))
        
        if away_shots_avg >= 15:
            recommendations.append(BettingRecommendation(
                market=f"{away_stats.team.name} Shots",
                selection="Over 13.5",
                confidence="MEDIUM",
                odds_range="1.80-2.30",
                reasoning=f"{away_stats.team.name}: {away_shots_avg:.1f} shots/match average",
                percentage=65.0
            ))
        
        return recommendations
    
    def _analyze_corners(self, home_stats: TeamStats, away_stats: TeamStats) -> List[BettingRecommendation]:
        """Analyze corners markets."""
        recommendations = []
        
        home_corners_avg = home_stats.corners_per_game
        away_corners_avg = away_stats.corners_per_game
        total_corners_expected = home_corners_avg + away_corners_avg
        
        if total_corners_expected == 0:
            return recommendations  # No corner data available
        
        # Total Corners Over/Under
        if total_corners_expected >= 12:
            recommendations.append(BettingRecommendation(
                market="Total Corners",
                selection="Over 10.5",
                confidence="HIGH",
                odds_range="1.60-2.00",
                reasoning=f"High corner volume: {total_corners_expected:.1f} corners/match",
                percentage=75.0
            ))
        elif total_corners_expected <= 8:
            recommendations.append(BettingRecommendation(
                market="Total Corners",
                selection="Under 9.5",
                confidence="MEDIUM",
                odds_range="1.70-2.20",
                reasoning=f"Low corner volume: {total_corners_expected:.1f} corners/match",
                percentage=65.0
            ))
        
        # Individual team corners
        if home_corners_avg >= 6:
            recommendations.append(BettingRecommendation(
                market=f"{home_stats.team.name} Corners",
                selection="Over 5.5",
                confidence="MEDIUM",
                odds_range="1.80-2.50",
                reasoning=f"{home_stats.team.name}: {home_corners_avg:.1f} corners/match",
                percentage=65.0
            ))
        
        return recommendations
    
    def _analyze_cards(self, home_stats: TeamStats, away_stats: TeamStats) -> List[BettingRecommendation]:
        """Analyze cards markets."""
        recommendations = []
        
        home_cards_avg = home_stats.yellow_cards_per_game
        away_cards_avg = away_stats.yellow_cards_per_game
        total_cards_expected = home_cards_avg + away_cards_avg
        
        # Total Cards Over/Under
        if total_cards_expected >= 5:
            recommendations.append(BettingRecommendation(
                market="Total Cards",
                selection="Over 4.5",
                confidence="HIGH",
                odds_range="1.70-2.20",
                reasoning=f"High card volume: {total_cards_expected:.1f} cards/match",
                percentage=75.0
            ))
        elif total_cards_expected <= 2.5:
            recommendations.append(BettingRecommendation(
                market="Total Cards",
                selection="Under 3.5",
                confidence="MEDIUM",
                odds_range="1.60-2.00",
                reasoning=f"Disciplined teams: {total_cards_expected:.1f} cards/match",
                percentage=65.0
            ))
        
        # Individual team cards
        if home_cards_avg >= 3:
            recommendations.append(BettingRecommendation(
                market=f"{home_stats.team.name} Cards",
                selection="Over 2.5",
                confidence="MEDIUM",
                odds_range="2.00-3.00",
                reasoning=f"{home_stats.team.name}: {home_cards_avg:.1f} cards/match (aggressive)",
                percentage=60.0
            ))
        
        if away_cards_avg >= 3:
            recommendations.append(BettingRecommendation(
                market=f"{away_stats.team.name} Cards",
                selection="Over 2.5",
                confidence="MEDIUM",
                odds_range="2.00-3.00",
                reasoning=f"{away_stats.team.name}: {away_cards_avg:.1f} cards/match (aggressive)",
                percentage=60.0
            ))
        
        return recommendations
    
    def _predict_exact_scores(self, home_stats: TeamStats, away_stats: TeamStats) -> List[ExactScorePrediction]:
        """Predict the most likely exact scores."""
        predictions = []
        
        # Calculate expected goals for each team
        home_goals_avg = home_stats.goals_per_game
        away_goals_avg = away_stats.goals_per_game
        home_conceded_avg = home_stats.goals_conceded_per_game
        away_conceded_avg = away_stats.goals_conceded_per_game
        
        # Adjust for home/away factors
        home_expected = (home_goals_avg + away_conceded_avg) / 2
        away_expected = (away_goals_avg + home_conceded_avg) / 2
        
        # Consider clean sheet and failed to score percentages
        home_clean_sheet_prob = home_stats.clean_sheet_percentage / 100
        away_clean_sheet_prob = away_stats.clean_sheet_percentage / 100
        home_fail_to_score_prob = home_stats.failed_to_score_percentage / 100
        away_fail_to_score_prob = away_stats.failed_to_score_percentage / 100
        
        # Generate score scenarios based on expected goals and probabilities
        score_probabilities = []
        
        # Common score scenarios to evaluate
        scenarios = [
            (0, 0), (1, 0), (0, 1), (1, 1), (2, 0), (0, 2), 
            (2, 1), (1, 2), (2, 2), (3, 0), (0, 3), (3, 1), (1, 3)
        ]
        
        for home_goals, away_goals in scenarios:
            probability = self._calculate_score_probability(
                home_goals, away_goals, home_expected, away_expected,
                home_clean_sheet_prob, away_clean_sheet_prob,
                home_fail_to_score_prob, away_fail_to_score_prob,
                home_stats, away_stats
            )
            
            if probability > 5.0:  # Only include reasonably probable scores
                score_probabilities.append({
                    'score': f"{home_goals}-{away_goals}",
                    'probability': probability,
                    'home_goals': home_goals,
                    'away_goals': away_goals
                })
        
        # Sort by probability and take top 2
        score_probabilities.sort(key=lambda x: x['probability'], reverse=True)
        top_scores = score_probabilities[:2]
        
        for score_data in top_scores:
            reasoning = self._generate_score_reasoning(
                score_data['home_goals'], score_data['away_goals'],
                home_stats, away_stats, home_expected, away_expected
            )
            
            # Estimate odds (rough approximation: odds = 100 / probability)
            odds_estimate = max(2.0, min(50.0, 100 / score_data['probability']))
            
            predictions.append(ExactScorePrediction(
                score=score_data['score'],
                probability=score_data['probability'],
                reasoning=reasoning,
                odds_estimate=f"{odds_estimate:.1f}"
            ))
        
        return predictions
    
    def _calculate_score_probability(self, home_goals, away_goals, home_expected, away_expected,
                                   home_clean_sheet_prob, away_clean_sheet_prob,
                                   home_fail_to_score_prob, away_fail_to_score_prob,
                                   home_stats, away_stats) -> float:
        """Calculate probability for a specific score."""
        import math
        
        # Base Poisson probability
        home_poisson = (home_expected ** home_goals) * math.exp(-home_expected) / math.factorial(home_goals)
        away_poisson = (away_expected ** away_goals) * math.exp(-away_expected) / math.factorial(away_goals)
        
        base_prob = home_poisson * away_poisson * 100
        
        # Adjust based on historical patterns
        
        # Boost 0-0 if both teams have high clean sheet rates and low scoring
        if home_goals == 0 and away_goals == 0:
            if home_clean_sheet_prob > 0.4 and away_clean_sheet_prob > 0.4:
                base_prob *= 1.5
            if home_fail_to_score_prob > 0.3 or away_fail_to_score_prob > 0.3:
                base_prob *= 1.3
        
        # Boost 1-0 or 0-1 for defensive teams
        if (home_goals == 1 and away_goals == 0) or (home_goals == 0 and away_goals == 1):
            avg_clean_sheet = (home_clean_sheet_prob + away_clean_sheet_prob) / 2
            if avg_clean_sheet > 0.3:
                base_prob *= 1.2
        
        # Reduce high-scoring probabilities for defensive teams
        total_goals = home_goals + away_goals
        if total_goals >= 3:
            avg_conceded = (home_stats.goals_conceded_per_game + away_stats.goals_conceded_per_game) / 2
            if avg_conceded < 1.0:
                base_prob *= 0.7
        
        # Boost 1-1 for evenly matched teams
        if home_goals == 1 and away_goals == 1:
            goal_diff = abs(home_stats.goals_per_game - away_stats.goals_per_game)
            if goal_diff < 0.5:  # Very similar scoring rates
                base_prob *= 1.2
        
        return min(base_prob, 25.0)  # Cap at 25% for any single score
    
    def _generate_score_reasoning(self, home_goals, away_goals, home_stats, away_stats, 
                                home_expected, away_expected) -> str:
        """Generate reasoning for a score prediction."""
        total_goals = home_goals + away_goals
        
        if home_goals == 0 and away_goals == 0:
            return f"Defensive match: {home_stats.clean_sheet_percentage:.0f}% vs {away_stats.clean_sheet_percentage:.0f}% clean sheets"
        
        elif home_goals == 1 and away_goals == 0:
            return f"Home win: {home_stats.team.name} averages {home_stats.goals_per_game:.1f} goals, solid defense"
        
        elif home_goals == 0 and away_goals == 1:
            return f"Away win: {away_stats.team.name} averages {away_stats.goals_per_game:.1f} goals vs weak home defense"
        
        elif home_goals == 1 and away_goals == 1:
            return f"Balanced match: Similar attacking strength ({home_expected:.1f} vs {away_expected:.1f} expected)"
        
        elif total_goals == 2:
            if home_goals > away_goals:
                return f"Home advantage: {home_stats.team.name} more clinical at home"
            else:
                return f"Away efficiency: {away_stats.team.name} clinical away from home"
        
        elif total_goals >= 3:
            return f"High-scoring: Both teams average {(home_stats.goals_per_game + away_stats.goals_per_game):.1f} goals combined"
        
        else:
            return f"Expected goals: {home_expected:.1f} vs {away_expected:.1f}"
    
    def _create_summary(self, recommendations: List[BettingRecommendation]) -> Dict[str, str]:
        """Create betting summary."""
        high_conf = [r for r in recommendations if r.confidence == "HIGH"]
        medium_conf = [r for r in recommendations if r.confidence == "MEDIUM"]
        
        return {
            "total_recommendations": str(len(recommendations)),
            "high_confidence": str(len(high_conf)),
            "medium_confidence": str(len(medium_conf)),
            "top_pick": high_conf[0].selection if high_conf else "None",
            "top_market": high_conf[0].market if high_conf else "None"
        }
