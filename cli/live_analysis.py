"""Live match analysis module."""

import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime

from adapters.football_api import FootballAPIClient
from core.analyzer import MatchAnalyzer
from betting.orchestrator import BettingOrchestrator
from cli.simple_main import display_betting_analysis


class LiveMatchAnalyzer:
    """Analyzer for live matches."""
    
    def __init__(self):
        self.api_client = FootballAPIClient()
        self.analyzer = MatchAnalyzer()
        self.orchestrator = BettingOrchestrator()
        
        # Top 5 European leagues + European competitions
        self.top_leagues = {
            135: "Serie A",           # Italy
            39: "Premier League",     # England  
            140: "La Liga",           # Spain
            78: "Bundesliga",         # Germany
            61: "Ligue 1",            # France
            2: "UEFA Champions League",
            3: "UEFA Europa League"
        }
    
    async def get_live_matches(self) -> List[Dict[str, Any]]:
        """Get current live matches from top leagues."""
        print("🔴 Searching for live matches in top European leagues...")
        
        live_fixtures = await self.api_client.get_live_fixtures(list(self.top_leagues.keys()))
        
        if not live_fixtures:
            print("📺 No live matches found at the moment in top European leagues.")
            print("💡 This could mean:")
            print("   • No matches are currently being played")
            print("   • Matches are in break time or finished")
            print("   • API is returning test/demo data")
            print("\n🔄 Try again later or use PRE-MATCH analysis for upcoming games.")
            return []
        
        print(f"🎬 Found {len(live_fixtures)} real live matches!")
        return live_fixtures
    
    def display_live_matches(self, live_fixtures: List[Dict[str, Any]]) -> None:
        """Display available live matches."""
        print("\n🔴 LIVE MATCHES")
        print("=" * 50)
        
        # Group by league
        leagues = {}
        for fixture in live_fixtures:
            league_name = fixture["league"]["name"]
            if league_name not in leagues:
                leagues[league_name] = []
            leagues[league_name].append(fixture)
        
        match_index = 1
        self.match_mapping = {}
        
        for league_name, matches in leagues.items():
            country = matches[0]["league"]["country"]
            flag = self._get_country_flag(country)
            
            print(f"\n{flag} {league_name.upper()}")
            print("-" * 40)
            
            for match in matches:
                status = self._format_match_status(match)
                score = self._format_score(match)
                
                print(f" {match_index}. {match['home_team']['name']} vs {match['away_team']['name']}")
                print(f"     {status} | {score}")
                print(f"     🏟️ {match['venue'] or 'Unknown Venue'}")
                
                self.match_mapping[match_index] = match
                match_index += 1
        
        print(f"\n0. Back to main menu")
    
    def _get_country_flag(self, country: str) -> str:
        """Get country flag emoji."""
        flags = {
            "Italy": "🇮🇹",
            "England": "🏴󠁧󠁢󠁥󠁮󠁧󠁿", 
            "Spain": "🇪🇸",
            "Germany": "🇩🇪",
            "France": "🇫🇷",
            "Europe": "🏆"
        }
        return flags.get(country, "🌍")
    
    def _format_match_status(self, match: Dict[str, Any]) -> str:
        """Format match status with emoji."""
        status = match.get("status", "LIVE")
        elapsed = match.get("elapsed")
        
        if status == "1H":
            return f"🟢 1st Half - {elapsed}'"
        elif status == "HT":
            return "⏸️ Half Time"
        elif status == "2H":
            return f"🟢 2nd Half - {elapsed}'"
        elif status == "ET":
            return f"⏰ Extra Time - {elapsed}'"
        elif status == "P":
            return "⚽ Penalties"
        else:
            return f"🔴 LIVE - {elapsed}'" if elapsed else "🔴 LIVE"
    
    def _format_score(self, match: Dict[str, Any]) -> str:
        """Format current score."""
        score = match.get("score", {})
        home_score = score.get("home", 0) or 0
        away_score = score.get("away", 0) or 0
        
        return f"{home_score}-{away_score}"
    
    async def analyze_live_match(self, match: Dict[str, Any]) -> None:
        """Analyze a specific live match."""
        home_team = match["home_team"]["name"]
        away_team = match["away_team"]["name"]
        league_name = match["league"]["name"]
        current_score = self._format_score(match)
        status = self._format_match_status(match)
        
        print(f"\n⏳ Analyzing live match: {home_team} vs {away_team}...")
        print(f"🏆 League: {league_name}")
        print(f"📊 Current: {current_score} | {status}")
        
        try:
            # Get league ID and season
            league_id = match["league"]["id"]
            season = 2025
            
            # Create fixture object for analysis
            from core.models import Fixture, Team
            from datetime import datetime
            import pytz
            
            fixture = Fixture(
                id=match["id"],
                date=datetime.now(pytz.UTC),
                status=match["status"],
                home_team=Team(
                    id=match["home_team"]["id"],
                    name=match["home_team"]["name"],
                    logo=match["home_team"]["logo"]
                ),
                away_team=Team(
                    id=match["away_team"]["id"],
                    name=match["away_team"]["name"],
                    logo=match["away_team"]["logo"]
                ),
                venue=match["venue"]
            )
            
            # Analyze the match
            prediction = await self.analyzer._analyze_single_match(fixture, league_id, season)
            
            # Display live match info
            self._display_live_match_header(match, prediction)
            
            # Generate live betting analysis (focused on main markets)
            live_analysis = await self._generate_live_betting_analysis(match, prediction, league_id, season)
            
            # Display live analysis
            self._display_live_betting_analysis(live_analysis)
            
        except Exception as e:
            print(f"❌ Error analyzing live match: {e}")
            import traceback
            traceback.print_exc()
    
    def _display_live_match_header(self, match: Dict[str, Any], prediction) -> None:
        """Display live match information header."""
        print("\n🔴 LIVE MATCH ANALYSIS")
        print("=" * 50)
        
        home_team = match["home_team"]["name"]
        away_team = match["away_team"]["name"]
        league_name = match["league"]["name"]
        current_score = self._format_score(match)
        status = self._format_match_status(match)
        
        print(f"\n🏆 {home_team} vs {away_team}")
        print(f"🏟️ {match['venue'] or 'Unknown Venue'}")
        print(f"🏆 {league_name}")
        print(f"📊 Current Score: {current_score}")
        print(f"⏱️ Status: {status}")
        
        # Show team stats comparison (abbreviated for live)
        if hasattr(prediction, 'home_stats') and hasattr(prediction, 'away_stats'):
            home_stats = prediction.home_stats
            away_stats = prediction.away_stats
            
            print(f"\n📈 SEASON STATS COMPARISON")
            print("-" * 30)
            print(f"Goals/Game:     {home_stats.goals_per_game:.1f} vs {away_stats.goals_per_game:.1f}")
            print(f"Goals Against:  {home_stats.goals_conceded_per_game:.1f} vs {away_stats.goals_conceded_per_game:.1f}")
            print(f"Cards/Game:     {home_stats.yellow_cards_per_game:.1f} vs {away_stats.yellow_cards_per_game:.1f}")
            print(f"Matches:        {home_stats.matches_played} vs {away_stats.matches_played}")
    
    async def _generate_live_betting_analysis(self, match: Dict[str, Any], prediction, league_id: int, season: int) -> Dict[str, Any]:
        """Generate focused betting analysis for live matches."""
        try:
            # Get live match statistics
            live_stats = await self.api_client.get_live_match_statistics(match["id"])
            
            # Get current score
            current_score = match.get("score", {})
            home_goals = current_score.get("home", 0) or 0
            away_goals = current_score.get("away", 0) or 0
            total_goals = home_goals + away_goals
            
            # Get match status and elapsed time
            status = match.get("status", "LIVE")
            elapsed = match.get("elapsed", 0) or 0
            
            # Generate live analysis
            analysis = {
                "match_info": {
                    "home_team": match["home_team"]["name"],
                    "away_team": match["away_team"]["name"],
                    "current_score": f"{home_goals}-{away_goals}",
                    "elapsed": elapsed,
                    "status": status
                },
                "live_stats": live_stats,
                "predictions": {
                    "result_1x2": self._analyze_live_1x2(match, prediction, live_stats, elapsed),
                    "under_over": self._analyze_live_under_over(match, prediction, live_stats, elapsed),
                    "btts": self._analyze_live_btts(match, prediction, live_stats, elapsed),
                    "next_goal": self._analyze_next_goal(match, prediction, live_stats, elapsed)
                }
            }
            
            return analysis
            
        except Exception as e:
            print(f"⚠️ Error generating live analysis: {e}")
            return {}
    
    def _analyze_live_1x2(self, match: Dict[str, Any], prediction, live_stats: Dict, elapsed: int) -> Dict[str, Any]:
        """Analyze 1X2 market based on live situation."""
        current_score = match.get("score", {})
        home_goals = current_score.get("home", 0) or 0
        away_goals = current_score.get("away", 0) or 0
        
        # Base probabilities from season stats
        home_stats = prediction.home_stats
        away_stats = prediction.away_stats
        
        # Adjust based on current situation
        if home_goals > away_goals:
            # Home leading
            home_prob = 60 + min((home_goals - away_goals) * 10, 25)
            draw_prob = max(25 - elapsed/4, 10)
            away_prob = 100 - home_prob - draw_prob
        elif away_goals > home_goals:
            # Away leading
            away_prob = 60 + min((away_goals - home_goals) * 10, 25)
            draw_prob = max(25 - elapsed/4, 10)
            home_prob = 100 - away_prob - draw_prob
        else:
            # Draw
            remaining_time = max(90 - elapsed, 0)
            if remaining_time > 30:
                home_prob = 40
                draw_prob = 30
                away_prob = 30
            else:
                home_prob = 35
                draw_prob = 40
                away_prob = 25
        
        return {
            "home_win": {"probability": home_prob, "odds": f"{100/home_prob:.2f}"},
            "draw": {"probability": draw_prob, "odds": f"{100/draw_prob:.2f}"},
            "away_win": {"probability": away_prob, "odds": f"{100/away_prob:.2f}"}
        }
    
    def _analyze_live_under_over(self, match: Dict[str, Any], prediction, live_stats: Dict, elapsed: int) -> Dict[str, Any]:
        """Analyze Under/Over markets based on live situation."""
        current_score = match.get("score", {})
        home_goals = current_score.get("home", 0) or 0
        away_goals = current_score.get("away", 0) or 0
        total_goals = home_goals + away_goals
        
        # Calculate goal rate
        if elapsed > 0:
            current_rate = (total_goals / elapsed) * 90
        else:
            current_rate = 0
        
        # Season averages
        home_stats = prediction.home_stats
        away_stats = prediction.away_stats
        expected_total = home_stats.goals_per_game + away_stats.goals_conceded_per_game
        
        # Adjust based on current situation
        remaining_time = max(90 - elapsed, 0)
        projected_goals = total_goals + (current_rate * remaining_time / 90)
        
        # Under/Over 2.5
        if projected_goals < 2.5:
            under_25_prob = 70 + min((2.5 - projected_goals) * 10, 20)
        else:
            under_25_prob = max(30 - (projected_goals - 2.5) * 10, 10)
        
        over_25_prob = 100 - under_25_prob
        
        return {
            "current_goals": total_goals,
            "projected_total": round(projected_goals, 1),
            "under_25": {"probability": under_25_prob, "odds": f"{100/under_25_prob:.2f}"},
            "over_25": {"probability": over_25_prob, "odds": f"{100/over_25_prob:.2f}"}
        }
    
    def _analyze_live_btts(self, match: Dict[str, Any], prediction, live_stats: Dict, elapsed: int) -> Dict[str, Any]:
        """Analyze Both Teams To Score based on live situation."""
        current_score = match.get("score", {})
        home_goals = current_score.get("home", 0) or 0
        away_goals = current_score.get("away", 0) or 0
        
        # Check if BTTS already achieved
        if home_goals > 0 and away_goals > 0:
            return {
                "btts_yes": {"probability": 100, "odds": "1.00", "status": "✅ Already achieved"},
                "btts_no": {"probability": 0, "odds": "N/A", "status": "❌ Not possible"}
            }
        
        # Calculate probability based on remaining time and team stats
        remaining_time = max(90 - elapsed, 0)
        
        if home_goals == 0 and away_goals == 0:
            # No goals yet
            btts_prob = max(40 - elapsed/3, 15)
        elif home_goals > 0 or away_goals > 0:
            # One team scored
            btts_prob = max(60 - elapsed/2, 25)
        
        btts_no_prob = 100 - btts_prob
        
        return {
            "btts_yes": {"probability": btts_prob, "odds": f"{100/btts_prob:.2f}"},
            "btts_no": {"probability": btts_no_prob, "odds": f"{100/btts_no_prob:.2f}"}
        }
    
    def _analyze_next_goal(self, match: Dict[str, Any], prediction, live_stats: Dict, elapsed: int) -> Dict[str, Any]:
        """Analyze who will score the next goal."""
        # Get live statistics for better prediction
        home_shots = live_stats.get("home", {}).get("total_shots", 0)
        away_shots = live_stats.get("away", {}).get("total_shots", 0)
        home_possession = live_stats.get("home", {}).get("possession", 50)
        away_possession = live_stats.get("away", {}).get("possession", 50)
        
        # Base probability on possession and shots
        if home_shots + away_shots > 0:
            home_prob = 30 + (home_shots / (home_shots + away_shots)) * 40
        else:
            home_prob = 30 + (home_possession / 100) * 20
        
        away_prob = 30 + (away_possession / 100) * 20
        no_goal_prob = 100 - home_prob - away_prob
        
        return {
            "home_next": {"probability": home_prob, "odds": f"{100/home_prob:.2f}"},
            "away_next": {"probability": away_prob, "odds": f"{100/away_prob:.2f}"},
            "no_goal": {"probability": no_goal_prob, "odds": f"{100/no_goal_prob:.2f}"}
        }
    
    def _display_live_betting_analysis(self, analysis: Dict[str, Any]) -> None:
        """Display focused live betting analysis."""
        if not analysis:
            return
        
        match_info = analysis.get("match_info", {})
        live_stats = analysis.get("live_stats", {})
        predictions = analysis.get("predictions", {})
        
        print(f"\n📊 LIVE STATISTICS")
        print("═" * 40)
        
        # Display live stats if available
        if live_stats:
            home_stats = live_stats.get("home", {})
            away_stats = live_stats.get("away", {})
            
            print(f"⚽ Shots:        {home_stats.get('total_shots', 0)} - {away_stats.get('total_shots', 0)}")
            print(f"🎯 On Target:    {home_stats.get('shots_on_target', 0)} - {away_stats.get('shots_on_target', 0)}")
            print(f"📐 Corners:      {home_stats.get('corners', 0)} - {away_stats.get('corners', 0)}")
            print(f"🏃 Possession:   {home_stats.get('possession', 0):.0f}% - {away_stats.get('possession', 0):.0f}%")
            print(f"🟨 Cards:        {home_stats.get('yellow_cards', 0)} - {away_stats.get('yellow_cards', 0)}")
        
        # 1X2 Analysis
        result_1x2 = predictions.get("result_1x2", {})
        if result_1x2:
            print(f"\n🏆 RESULT (1X2)")
            print("━" * 25)
            home_win = result_1x2.get("home_win", {})
            draw = result_1x2.get("draw", {})
            away_win = result_1x2.get("away_win", {})
            
            print(f"🏠 Home Win:     {home_win.get('probability', 0):.1f}% │ 💰 {home_win.get('odds', 'N/A')}")
            print(f"🤝 Draw:         {draw.get('probability', 0):.1f}% │ 💰 {draw.get('odds', 'N/A')}")
            print(f"✈️ Away Win:     {away_win.get('probability', 0):.1f}% │ 💰 {away_win.get('odds', 'N/A')}")
        
        # Under/Over Analysis
        under_over = predictions.get("under_over", {})
        if under_over:
            print(f"\n⚽ GOALS (Under/Over 2.5)")
            print("━" * 30)
            print(f"📊 Current: {under_over.get('current_goals', 0)} │ Projected: {under_over.get('projected_total', 0)}")
            
            under_25 = under_over.get("under_25", {})
            over_25 = under_over.get("over_25", {})
            
            print(f"📉 Under 2.5:    {under_25.get('probability', 0):.1f}% │ 💰 {under_25.get('odds', 'N/A')}")
            print(f"📈 Over 2.5:     {over_25.get('probability', 0):.1f}% │ 💰 {over_25.get('odds', 'N/A')}")
        
        # BTTS Analysis
        btts = predictions.get("btts", {})
        if btts:
            print(f"\n🎯 BOTH TEAMS TO SCORE")
            print("━" * 25)
            
            btts_yes = btts.get("btts_yes", {})
            btts_no = btts.get("btts_no", {})
            
            status_yes = btts_yes.get("status", "")
            status_no = btts_no.get("status", "")
            
            print(f"✅ BTTS Yes:     {btts_yes.get('probability', 0):.1f}% │ 💰 {btts_yes.get('odds', 'N/A')} {status_yes}")
            print(f"❌ BTTS No:      {btts_no.get('probability', 0):.1f}% │ 💰 {btts_no.get('odds', 'N/A')} {status_no}")
        
        # Next Goal Analysis
        next_goal = predictions.get("next_goal", {})
        if next_goal:
            print(f"\n⚡ NEXT GOAL")
            print("━" * 15)
            
            home_next = next_goal.get("home_next", {})
            away_next = next_goal.get("away_next", {})
            no_goal = next_goal.get("no_goal", {})
            
            print(f"🏠 Home:         {home_next.get('probability', 0):.1f}% │ 💰 {home_next.get('odds', 'N/A')}")
            print(f"✈️ Away:         {away_next.get('probability', 0):.1f}% │ 💰 {away_next.get('odds', 'N/A')}")
            print(f"⏸️ No Goal:      {no_goal.get('probability', 0):.1f}% │ 💰 {no_goal.get('odds', 'N/A')}")


async def run_live_analysis():
    """Run live match analysis."""
    analyzer = LiveMatchAnalyzer()
    
    while True:
        try:
            # Get live matches
            live_matches = await analyzer.get_live_matches()
            
            if not live_matches:
                print("\n📺 No live matches available at the moment.")
                print("🔄 Try again later or switch to pre-match analysis.")
                return
            
            # Display live matches
            analyzer.display_live_matches(live_matches)
            
            # Get user choice
            print(f"\n🎯 Choose a live match to analyze (1-{len(live_matches)}, 0 to go back): ", end="")
            choice = input().strip()
            
            if choice == "0":
                break
            
            try:
                match_num = int(choice)
                if 1 <= match_num <= len(live_matches):
                    selected_match = analyzer.match_mapping[match_num]
                    await analyzer.analyze_live_match(selected_match)
                    
                    # Ask if user wants to analyze another match
                    print("\n" + "=" * 50)
                    continue_choice = input("🔄 Analyze another live match? (s/n): ").strip().lower()
                    if continue_choice not in ['s', 'si', 'y', 'yes']:
                        break
                else:
                    print("❌ Invalid choice. Please try again.")
            except ValueError:
                print("❌ Invalid input. Please enter a number.")
                
        except KeyboardInterrupt:
            print("\n👋 Live analysis interrupted.")
            break
        except Exception as e:
            print(f"❌ Error in live analysis: {e}")
            break
