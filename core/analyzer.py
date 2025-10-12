"""Core analysis logic for match predictions."""

from typing import List
import asyncio

from .models import Fixture, TeamStats, MatchPrediction
from adapters.football_api import FootballAPIClient


class MatchAnalyzer:
    """Analyzes matches and calculates predictions."""
    
    def __init__(self):
        self.api_client = FootballAPIClient()
    
    async def analyze_next_matchday(self, league_id: int = None, season: int = None, country: str = None) -> tuple[List[MatchPrediction], int]:
        """Analyze all matches in the next matchday."""
        # Get next round fixtures
        fixtures, round_number = await self.api_client.get_next_round_fixtures(league_id, season, country)
        
        # Analyze matches sequentially to avoid rate limiting
        predictions = []
        for fixture in fixtures:
            try:
                prediction = await self._analyze_single_match(fixture, league_id, season)
                predictions.append(prediction)
            except Exception as e:
                print(f"⚠️ Errore nell'analisi di {fixture.home_team.name} vs {fixture.away_team.name}: {e}")
                continue
        
        return predictions, round_number
    
    async def _analyze_single_match(self, fixture: Fixture, league_id: int = None, season: int = None) -> MatchPrediction:
        """Analyze a single match."""
        # Get statistics for both teams sequentially to avoid rate limiting
        home_stats = await self.api_client.get_team_statistics(fixture.home_team.id, league_id, season)
        away_stats = await self.api_client.get_team_statistics(fixture.away_team.id, league_id, season)
        
        # Se non abbiamo statistiche per una squadra, marca come TO AVOID
        if not home_stats or not away_stats:
            missing_teams = []
            if not home_stats:
                missing_teams.append(fixture.home_team.name)
            if not away_stats:
                missing_teams.append(fixture.away_team.name)
            
            print(f"⚠️ Match {fixture.home_team.name} vs {fixture.away_team.name} marked as TO AVOID (missing stats: {', '.join(missing_teams)})")
            
            return MatchPrediction(
                fixture=fixture,
                home_stats=None,
                away_stats=None,
                expected_total_goals=0.0,
                expected_total_corners=0.0,
                expected_total_yellow_cards=0.0,
                status="TO AVOID",
                warning=f"⚠️ Statistiche mancanti: {', '.join(missing_teams)}",
                untracked_teams=missing_teams
            )
        
        # Calculate expected statistics
        expected_total_goals = self._calculate_expected_goals(home_stats, away_stats)
        expected_total_corners = self._calculate_expected_corners(home_stats, away_stats)
        expected_total_yellow_cards = self._calculate_expected_yellow_cards(home_stats, away_stats)
        
        return MatchPrediction(
            fixture=fixture,
            home_stats=home_stats,
            away_stats=away_stats,
            expected_total_goals=expected_total_goals,
            expected_total_corners=expected_total_corners,
            expected_total_yellow_cards=expected_total_yellow_cards,
            status="ANALYZABLE"
        )
    
    def _calculate_expected_goals(self, home_stats: TeamStats, away_stats: TeamStats) -> float:
        """Calculate expected total goals for a match."""
        # Simple average of goals per game for both teams
        home_goals_avg = home_stats.goals_per_game
        away_goals_avg = away_stats.goals_per_game
        
        # Consider defensive strength
        home_conceded_avg = home_stats.goals_conceded_per_game
        away_conceded_avg = away_stats.goals_conceded_per_game
        
        # Expected goals = (team's scoring rate + opponent's conceding rate) / 2
        expected_home_goals = (home_goals_avg + away_conceded_avg) / 2
        expected_away_goals = (away_goals_avg + home_conceded_avg) / 2
        
        return round(expected_home_goals + expected_away_goals, 2)
    
    def _calculate_expected_corners(self, home_stats: TeamStats, away_stats: TeamStats) -> float:
        """Calculate expected total corners for a match."""
        # Simple average of corners per game for both teams
        home_corners_avg = home_stats.corners_per_game
        away_corners_avg = away_stats.corners_per_game
        
        # Only calculate if we have corner data
        if home_corners_avg == 0 and away_corners_avg == 0:
            return 0.0
            
        return round(home_corners_avg + away_corners_avg, 2)
    
    def _calculate_expected_yellow_cards(self, home_stats: TeamStats, away_stats: TeamStats) -> float:
        """Calculate expected total yellow cards for a match."""
        # Simple average of yellow cards per game for both teams
        home_yellows_avg = home_stats.yellow_cards_per_game
        away_yellows_avg = away_stats.yellow_cards_per_game
        
        return round(home_yellows_avg + away_yellows_avg, 2)
    
