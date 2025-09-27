"""Simplified CLI application using only Typer without Rich."""

import typer
import asyncio
from typing import Optional
import sys

from core.analyzer import MatchAnalyzer
from core.config import get_settings
from adapters.football_api import FootballAPIError


def main():
    """Main CLI function."""
    if len(sys.argv) == 1 or (len(sys.argv) == 2 and sys.argv[1] in ["--help", "-h"]):
        print("⚽ Footy Predictor CLI")
        print("Usage:")
        print("  python main.py interactive    # Menu interattivo (RACCOMANDATO)")
        print("  python main.py matchday [OPTIONS]")
        print("  python main.py config")
        print("")
        print("Commands:")
        print("  interactive  Menu interattivo per scegliere campionato e partita")
        print("  matchday     Analizza tutte le partite della prossima giornata")
        print("  config       Mostra configurazione corrente")
        print("  cache        Mostra statistiche cache database")
        print("  bookmakers   Mostra tutti i bookmaker disponibili")
        print("  bets         Mostra tutti i mercati di scommessa disponibili")
        print("  players      Mostra statistiche database giocatori")
        print("")
        print("Options for matchday:")
        print("  --league, -l    League name (e.g., 'Serie A')")
        print("  --country, -c   Country name (e.g., 'Italy')")
        print("  --season, -s    Season year (e.g., 2025)")
        return
    
    command = sys.argv[1]
    
    if command == "interactive":
        from cli.interactive import run_interactive_menu
        asyncio.run(run_interactive_menu())
    
    elif command == "matchday":
        # Parse options
        league = None
        country = None
        season = None
        
        i = 2
        while i < len(sys.argv):
            if sys.argv[i] in ["--league", "-l"] and i + 1 < len(sys.argv):
                league = sys.argv[i + 1]
                i += 2
            elif sys.argv[i] in ["--country", "-c"] and i + 1 < len(sys.argv):
                country = sys.argv[i + 1]
                i += 2
            elif sys.argv[i] in ["--season", "-s"] and i + 1 < len(sys.argv):
                season = int(sys.argv[i + 1])
                i += 2
            else:
                i += 1
        
        asyncio.run(analyze_matchday(league, country, season))
    
    elif command == "config":
        show_config()
    
    elif command == "cache":
        show_cache_stats()
    
    elif command == "bookmakers":
        asyncio.run(show_bookmakers())
    
    elif command == "bets":
        asyncio.run(show_available_bets())
    
    elif command == "players":
        show_player_database_stats()
    
    else:
        print(f"Unknown command: {command}")
        print("Use 'python main.py --help' for usage information.")


async def analyze_matchday(league: Optional[str], country: Optional[str], season: Optional[int]):
    """Analyze matchday."""
    try:
        settings = get_settings()
        analyzer = MatchAnalyzer()
        
        # Display loading message
        league_name = league or settings.default_league
        country_name = country or settings.default_country
        season_year = season or settings.default_season
        
        print(f"⏳ Fetching data for {league_name} ({country_name}) - Season {season_year}...")
        
        # Get league ID if custom league/country specified
        league_id = None
        if league or country:
            league_id = await analyzer.api_client.get_league_id(country_name, league_name, season_year)
        
        # Analyze next matchday
        predictions = await analyzer.analyze_next_matchday(league_id, season_year)
        
        # Display results
        await display_matchday(predictions, league_id, season_year)
        
    except FootballAPIError as e:
        print(f"❌ API Error: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")


async def display_matchday(predictions, league_id=None, season=None):
    """Display matchday predictions."""
    if not predictions:
        print("⚠️ Nessuna partita trovata.")
        return
    
    print("\n⚽ PARTITE DISPONIBILI - ANALISI")
    print("=" * 50)
    
    for i, prediction in enumerate(predictions, 1):
        fixture = prediction.fixture
        home_stats = prediction.home_stats
        away_stats = prediction.away_stats
        
        print(f"\n🏆 Match {i}: {fixture.home_team.name} vs {fixture.away_team.name}")
        print(f"📅 {fixture.date.strftime('%d/%m/%Y %H:%M')}")
        if fixture.venue:
            print(f"🏟️ {fixture.venue}")
        
        print("\n📊 TEAM STATISTICS COMPARISON")
        print("-" * 40)
        
        # Format statistics in a table-like format
        stats_data = [
            ("Statistic", "🏠 " + home_stats.team.name, "✈️ " + away_stats.team.name),
            ("Matches Played", str(home_stats.matches_played), str(away_stats.matches_played)),
            ("Goals For/Against", f"{home_stats.goals_for}/{home_stats.goals_against}", 
             f"{away_stats.goals_for}/{away_stats.goals_against}"),
            ("Goals per Game", f"{home_stats.goals_per_game:.2f}", f"{away_stats.goals_per_game:.2f}"),
            ("Goals Conceded/Game", f"{home_stats.goals_conceded_per_game:.2f}", 
             f"{away_stats.goals_conceded_per_game:.2f}"),
            ("Recent Form", home_stats.form[-10:] if home_stats.form else "N/A", 
             away_stats.form[-10:] if away_stats.form else "N/A"),
            ("Form Points (L5)", str(home_stats.recent_form_points), str(away_stats.recent_form_points)),
            ("Clean Sheets", f"{home_stats.clean_sheets} ({home_stats.clean_sheet_percentage:.1f}%)", 
             f"{away_stats.clean_sheets} ({away_stats.clean_sheet_percentage:.1f}%)"),
            ("Failed to Score", f"{home_stats.failed_to_score} ({home_stats.failed_to_score_percentage:.1f}%)", 
             f"{away_stats.failed_to_score} ({away_stats.failed_to_score_percentage:.1f}%)"),
            ("Penalties", f"{home_stats.penalties_scored}/{home_stats.penalties_scored + home_stats.penalties_missed}", 
             f"{away_stats.penalties_scored}/{away_stats.penalties_scored + away_stats.penalties_missed}"),
            ("Penalty Success", f"{home_stats.penalty_conversion_rate:.1f}%", 
             f"{away_stats.penalty_conversion_rate:.1f}%"),
            ("Total Yellow Cards", str(home_stats.yellow_cards), str(away_stats.yellow_cards)),
            ("Yellow Cards/Game", f"{home_stats.yellow_cards_per_game:.2f}", 
             f"{away_stats.yellow_cards_per_game:.2f}"),
            ("Total Red Cards", str(home_stats.red_cards), str(away_stats.red_cards)),
            ("Over 1.5 Goals", f"{home_stats.over_1_5_goals_percentage:.1f}%", 
             f"{away_stats.over_1_5_goals_percentage:.1f}%"),
            ("Over 2.5 Goals", f"{home_stats.over_2_5_goals_percentage:.1f}%", 
             f"{away_stats.over_2_5_goals_percentage:.1f}%"),
            ("Over 3.5 Goals", f"{home_stats.over_3_5_goals_percentage:.1f}%", 
             f"{away_stats.over_3_5_goals_percentage:.1f}%"),
            ("Over 1.5 Conceded", f"{home_stats.over_1_5_conceded_percentage:.1f}%", 
             f"{away_stats.over_1_5_conceded_percentage:.1f}%"),
                   ("Over 2.5 Conceded", f"{home_stats.over_2_5_conceded_percentage:.1f}%", 
                    f"{away_stats.over_2_5_conceded_percentage:.1f}%"),
                   ("Total Shots", str(home_stats.shots_total), str(away_stats.shots_total)),
                   ("Shots per Game", f"{home_stats.shots_per_game:.2f}", f"{away_stats.shots_per_game:.2f}"),
                   ("Shots on Target", str(home_stats.shots_on_target), str(away_stats.shots_on_target)),
                   ("Shots on Target/Game", f"{home_stats.shots_on_target_per_game:.2f}", f"{away_stats.shots_on_target_per_game:.2f}"),
                   ("Total Corners", str(home_stats.corners), str(away_stats.corners)),
                   ("Corners per Game", f"{home_stats.corners_per_game:.2f}", f"{away_stats.corners_per_game:.2f}"),
                   ("W-D-L Record", f"{home_stats.wins}W-{home_stats.draws}D-{home_stats.losses}L",
                    f"{away_stats.wins}W-{away_stats.draws}D-{away_stats.losses}L")
        ]
        
        # Print table
        for row in stats_data:
            print(f"{row[0]:<20} {row[1]:<15} {row[2]:<15}")
        
        print("\n🔮 EXPECTED COMBINED STATS")
        print("-" * 30)
        print(f"Total Goals:        {prediction.expected_total_goals}")
        if prediction.expected_total_corners > 0:
            print(f"Total Corners:      {prediction.expected_total_corners}")
        print(f"Total Yellow Cards: {prediction.expected_total_yellow_cards}")
        
        if prediction.expected_total_corners == 0:
            print("📝 Note: Corner statistics calcolati dalle ultime partite quando disponibili")
        
        # Add betting predictions
        await display_betting_predictions_async(prediction, league_id, season)
        
        if i < len(predictions):
            print("\n" + "=" * 50)


async def display_betting_predictions_async(prediction, league_id=None, season=None):
    """Display betting predictions for a match (async version)."""
    from core.betting_predictions import BettingPredictor
    
    predictor = BettingPredictor()
    # Use provided parameters or try to get from prediction context
    if league_id is None:
        league_id = getattr(prediction, 'league_id', None)
    if season is None:
        season = getattr(prediction, 'season', 2025)
    
    betting_analysis = await predictor.analyze_match(prediction, league_id, season)
    
    # Try to enhance with real odds if fixture ID is available
    if hasattr(prediction.fixture, 'id'):
        try:
            betting_analysis = await predictor.enhance_with_real_odds(betting_analysis, prediction.fixture.id)
        except Exception as e:
            print(f"⚠️ Could not fetch real odds: {e}")
    
    # Now display the betting analysis
    display_betting_analysis(betting_analysis)
    
    return betting_analysis


def display_betting_analysis(betting_analysis):
    """Display the complete betting analysis including player predictions."""
    if not betting_analysis.recommendations:
        return
    
    print("\n🎯 BETTING RECOMMENDATIONS")
    print("═" * 50)
    
    # Group by confidence
    high_conf = [r for r in betting_analysis.recommendations if r.confidence == "HIGH"]
    medium_conf = [r for r in betting_analysis.recommendations if r.confidence == "MEDIUM"]
    low_conf = [r for r in betting_analysis.recommendations if r.confidence == "LOW"]
    
    if high_conf:
        print("\n🔥 HIGH CONFIDENCE PICKS:")
        print("━" * 35)
        for i, rec in enumerate(high_conf, 1):
            # Market type emoji
            market_emoji = {
                "Goals": "⚽",
                "BTTS": "🎯", 
                "Corners": "📐",
                "Cards": "🟨",
                "Shots": "🏹"
            }
            
            # Find appropriate emoji for market
            emoji = "📊"
            for key, value in market_emoji.items():
                if key.lower() in rec.market.lower():
                    emoji = value
                    break
            
            print(f"{i}. {emoji} {rec.market}: {rec.selection}")
            
            # Show estimated vs real odds with color coding
            percentage_color = "🔴" if rec.percentage >= 75 else "🟠" if rec.percentage >= 60 else "🟡"
            odds_display = f"   💰 Est: {rec.odds_range} │ {percentage_color} {rec.percentage:.1f}%"
            
            if rec.real_odds:
                value_emoji = {"EXCELLENT": "💎", "GOOD": "✨", "FAIR": "👍", "POOR": "⚠️"}.get(rec.value_rating, "")
                odds_display += f"\n   🏦 Real: {rec.real_odds} ({rec.bookmaker}) {value_emoji} {rec.value_rating}"
            print(odds_display)
            
            print(f"   💬 {rec.reasoning}")
            print()
    
    if medium_conf:
        print("⚡ MEDIUM CONFIDENCE PICKS:")
        print("━" * 35)
        for i, rec in enumerate(medium_conf, 1):
            # Market type emoji
            market_emoji = {
                "Goals": "⚽",
                "BTTS": "🎯", 
                "Corners": "📐",
                "Cards": "🟨",
                "Shots": "🏹"
            }
            
            # Find appropriate emoji for market
            emoji = "📊"
            for key, value in market_emoji.items():
                if key.lower() in rec.market.lower():
                    emoji = value
                    break
            
            print(f"{i}. {emoji} {rec.market}: {rec.selection}")
            
            # Show estimated vs real odds with color coding
            percentage_color = "🟠" if rec.percentage >= 65 else "🟡" if rec.percentage >= 55 else "🟢"
            odds_display = f"   💰 Est: {rec.odds_range} │ {percentage_color} {rec.percentage:.1f}%"
            
            if rec.real_odds:
                value_emoji = {"EXCELLENT": "💎", "GOOD": "✨", "FAIR": "👍", "POOR": "⚠️"}.get(rec.value_rating, "")
                odds_display += f"\n   🏦 Real: {rec.real_odds} ({rec.bookmaker}) {value_emoji} {rec.value_rating}"
            print(odds_display)
            
            print(f"   💬 {rec.reasoning}")
            print()
    
    # Exact score predictions
    if hasattr(betting_analysis, 'exact_scores') and betting_analysis.exact_scores:
        print("\n⚽ EXACT SCORE PREDICTIONS:")
        print("═" * 40)
        for i, score_pred in enumerate(betting_analysis.exact_scores[:2], 1):
            # Score result emoji
            home_score, away_score = score_pred.score.split('-')
            if int(home_score) > int(away_score):
                result_emoji = "🏠"  # Home win
            elif int(home_score) < int(away_score):
                result_emoji = "✈️"  # Away win
            else:
                result_emoji = "🤝"  # Draw
            
            # Probability color coding
            prob_color = "🔴" if score_pred.probability >= 15 else "🟠" if score_pred.probability >= 10 else "🟡"
            
            print(f"{i}. {result_emoji} {score_pred.score}")
            print(f"   {prob_color} Probability: {score_pred.probability:.1f}% │ 💰 Odds: {score_pred.odds_estimate}")
            print(f"   💬 {score_pred.reasoning}")
            print()
    
    # Player predictions
    if hasattr(betting_analysis, 'player_predictions') and betting_analysis.player_predictions:
        display_player_predictions(betting_analysis.player_predictions)
    
    # Summary
    print("📋 BETTING SUMMARY:")
    print("-" * 20)
    print(f"Total Recommendations: {betting_analysis.summary['total_recommendations']}")
    print(f"High Confidence: {betting_analysis.summary['high_confidence']}")
    print(f"Medium Confidence: {betting_analysis.summary['medium_confidence']}")
    print(f"🎯 Most Likely Score: {betting_analysis.summary.get('most_likely_score', 'N/A')}")
    print(f"🏆 Top Pick: {betting_analysis.summary.get('top_pick', 'N/A')}")


def display_betting_predictions(prediction):
    """Display betting predictions for a match."""
    print("🔍 DEBUG: display_betting_predictions called")
    # This should never be called since we're already in async context
    print("❌ ERROR: display_betting_predictions called instead of display_betting_predictions_async!")
    return None

def display_betting_predictions_sync(prediction):
    """Synchronous fallback version using historical data only."""
    from core.betting_predictions import BettingPredictor
    
    predictor = BettingPredictor()
    betting_analysis = predictor._generate_betting_analysis_sync(prediction)
    
    # TODO: Integrate real odds in a proper async context
    
    print("🔍 DEBUG: display_betting_predictions_sync called")
    
    if not betting_analysis.recommendations:
        print("🔍 DEBUG: No recommendations, returning early")
        return
    
    print("🔍 DEBUG: About to display betting recommendations")
    print("\n🎯 BETTING RECOMMENDATIONS")
    print("=" * 50)
    
    # Group by confidence
    high_conf = [r for r in betting_analysis.recommendations if r.confidence == "HIGH"]
    medium_conf = [r for r in betting_analysis.recommendations if r.confidence == "MEDIUM"]
    low_conf = [r for r in betting_analysis.recommendations if r.confidence == "LOW"]
    
    if high_conf:
        print("\n🔥 HIGH CONFIDENCE PICKS:")
        print("-" * 30)
        for rec in high_conf:
            confidence_emoji = "🔥"
            print(f"{confidence_emoji} {rec.market}: {rec.selection}")
            
            # Show estimated vs real odds
            odds_display = f"💰 Est: {rec.odds_range} | 📊 {rec.percentage:.1f}%"
            if rec.real_odds:
                value_emoji = {"EXCELLENT": "💎", "GOOD": "✨", "FAIR": "👍", "POOR": "⚠️"}.get(rec.value_rating, "")
                odds_display += f"\n   🏦 Real: {rec.real_odds} ({rec.bookmaker}) {value_emoji} {rec.value_rating}"
            print(f"   {odds_display}")
            
            print(f"   📝 {rec.reasoning}")
            print()
    
    if medium_conf:
        print("⚡ MEDIUM CONFIDENCE PICKS:")
        print("-" * 30)
        for rec in medium_conf:
            confidence_emoji = "⚡"
            print(f"{confidence_emoji} {rec.market}: {rec.selection}")
            
            # Show estimated vs real odds
            odds_display = f"💰 Est: {rec.odds_range} | 📊 {rec.percentage:.1f}%"
            if rec.real_odds:
                value_emoji = {"EXCELLENT": "💎", "GOOD": "✨", "FAIR": "👍", "POOR": "⚠️"}.get(rec.value_rating, "")
                odds_display += f"\n   🏦 Real: {rec.real_odds} ({rec.bookmaker}) {value_emoji} {rec.value_rating}"
            print(f"   {odds_display}")
            
            print(f"   📝 {rec.reasoning}")
            print()
    
    if low_conf:
        print("💡 LOW CONFIDENCE PICKS:")
        print("-" * 30)
        for rec in low_conf:
            confidence_emoji = "💡"
            print(f"{confidence_emoji} {rec.market}: {rec.selection}")
            
            # Show estimated vs real odds
            odds_display = f"💰 Est: {rec.odds_range} | 📊 {rec.percentage:.1f}%"
            if rec.real_odds:
                value_emoji = {"EXCELLENT": "💎", "GOOD": "✨", "FAIR": "👍", "POOR": "⚠️"}.get(rec.value_rating, "")
                odds_display += f"\n   🏦 Real: {rec.real_odds} ({rec.bookmaker}) {value_emoji} {rec.value_rating}"
            print(f"   {odds_display}")
            
            print(f"   📝 {rec.reasoning}")
            print()
    
    # Exact Score Predictions
    if betting_analysis.exact_scores:
        print("\n⚽ EXACT SCORE PREDICTIONS:")
        print("=" * 35)
        for i, score_pred in enumerate(betting_analysis.exact_scores, 1):
            print(f"{i}. {score_pred.score}")
            print(f"   📊 Probability: {score_pred.probability:.1f}%")
            print(f"   💰 Estimated Odds: {score_pred.odds_estimate}")
            print(f"   📝 {score_pred.reasoning}")
            print()
    
    # Player predictions
    print(f"🔍 DEBUG: player_predictions = {getattr(betting_analysis, 'player_predictions', 'NOT_FOUND')}")
    if hasattr(betting_analysis, 'player_predictions') and betting_analysis.player_predictions:
        print("🔍 DEBUG: Calling display_player_predictions")
        display_player_predictions(betting_analysis.player_predictions)
    else:
        print("🔍 DEBUG: No player predictions found")
    
    # Summary
    print("📋 BETTING SUMMARY:")
    print("-" * 20)
    print(f"Total Recommendations: {betting_analysis.summary['total_recommendations']}")
    print(f"High Confidence: {betting_analysis.summary['high_confidence']}")
    print(f"Medium Confidence: {betting_analysis.summary['medium_confidence']}")
    if betting_analysis.exact_scores:
        print(f"🎯 Most Likely Score: {betting_analysis.exact_scores[0].score} ({betting_analysis.exact_scores[0].probability:.1f}%)")
    if betting_analysis.summary['top_pick'] != "None":
        print(f"🏆 Top Pick: {betting_analysis.summary['top_market']} - {betting_analysis.summary['top_pick']}")


def display_player_predictions(player_predictions):
    """Display player card predictions for a match."""
    print("\n🟨 PLAYER CARD PREDICTIONS")
    print("=" * 50)
    
    # Home team top 3
    print(f"\n🏠 {player_predictions.fixture.home_team.name.upper()} - TOP 3 PLAYERS:")
    print("─" * 45)
    home_top3 = player_predictions.home_predictions[:3]
    for i, pred in enumerate(home_top3, 1):
        confidence_emoji = {"HIGH": "🔥", "MEDIUM": "⚡", "LOW": "💫"}.get(pred.confidence, "")
        confidence_color = {"HIGH": "🟥", "MEDIUM": "🟨", "LOW": "🟦"}.get(pred.confidence, "")
        
        # Position emoji
        position_emoji = {
            "defender": "🛡️", 
            "midfielder": "⚽", 
            "forward": "🎯", 
            "goalkeeper": "🥅"
        }.get(pred.player.position.lower(), "👤")
        
        print(f"{i}. {position_emoji} {pred.player.name}")
        print(f"   {confidence_emoji} {confidence_color} {pred.confidence} │ 📊 {pred.percentage:.1f}% │ 💰 {pred.estimated_odds}")
        print(f"   💬 {pred.reasoning}")
        print()
    
    # Away team top 3
    print(f"✈️ {player_predictions.fixture.away_team.name.upper()} - TOP 3 PLAYERS:")
    print("─" * 45)
    away_top3 = player_predictions.away_predictions[:3]
    for i, pred in enumerate(away_top3, 1):
        confidence_emoji = {"HIGH": "🔥", "MEDIUM": "⚡", "LOW": "💫"}.get(pred.confidence, "")
        confidence_color = {"HIGH": "🟥", "MEDIUM": "🟨", "LOW": "🟦"}.get(pred.confidence, "")
        
        # Position emoji
        position_emoji = {
            "defender": "🛡️", 
            "midfielder": "⚽", 
            "forward": "🎯", 
            "goalkeeper": "🥅"
        }.get(pred.player.position.lower(), "👤")
        
        print(f"{i}. {position_emoji} {pred.player.name}")
        print(f"   {confidence_emoji} {confidence_color} {pred.confidence} │ 📊 {pred.percentage:.1f}% │ 💰 {pred.estimated_odds}")
        print(f"   💬 {pred.reasoning}")
        print()
    
    # Overall top picks - SORTED BY PERCENTAGE (DESCENDING)
    all_predictions = player_predictions.home_predictions + player_predictions.away_predictions
    high_confidence_sorted = [p for p in all_predictions if p.confidence == "HIGH"]
    high_confidence_sorted.sort(key=lambda x: x.percentage, reverse=True)
    
    if high_confidence_sorted:
        print("🎯 OVERALL HIGH CONFIDENCE PICKS:")
        print("─" * 40)
        print("📈 Ordered by probability (highest first)")
        print()
        
        for i, pred in enumerate(high_confidence_sorted, 1):
            team_emoji = "🏠" if pred.player.team_id == player_predictions.fixture.home_team.id else "✈️"
            team_name = player_predictions.fixture.home_team.name if pred.player.team_id == player_predictions.fixture.home_team.id else player_predictions.fixture.away_team.name
            
            # Position emoji
            position_emoji = {
                "defender": "🛡️", 
                "midfielder": "⚽", 
                "forward": "🎯", 
                "goalkeeper": "🥅"
            }.get(pred.player.position.lower(), "👤")
            
            # Percentage color coding
            if pred.percentage >= 80:
                percentage_emoji = "🔴"  # Very high
            elif pred.percentage >= 60:
                percentage_emoji = "🟠"  # High
            elif pred.percentage >= 40:
                percentage_emoji = "🟡"  # Medium-high
            else:
                percentage_emoji = "🟢"  # Medium
            
            print(f"{i}. {team_emoji} {position_emoji} {pred.player.name} ({team_name})")
            print(f"   {percentage_emoji} {pred.percentage:.1f}% │ 💰 {pred.estimated_odds} │ 🔥 {pred.confidence}")
        print()


def show_config():
    """Show current configuration."""
    try:
        settings = get_settings()
        
        print("🔧 CURRENT CONFIGURATION")
        print("=" * 30)
        print(f"API Base URL:     {settings.api_football_base}")
        print(f"API Key:          {'*' * (len(settings.api_football_key) - 4)}{settings.api_football_key[-4:]}")
        print(f"Default Country:  {settings.default_country}")
        print(f"Default League:   {settings.default_league}")
        print(f"Default Season:   {settings.default_season}")
        print(f"Primary Bookmaker: {settings.primary_bookmaker} (Bet365)")
        print(f"Preferred Bookmakers: {settings.preferred_bookmakers} (Bet365 only)")
        
    except Exception as e:
        print(f"❌ Configuration error: {e}")


def show_cache_stats():
    """Show database cache statistics."""
    try:
        import os
        from utils.database import ShotsCornerCache
        
        db = ShotsCornerCache()
        stats = db.get_cache_stats()
        
        print("\n💾 DATABASE CACHE STATISTICS")
        print("=" * 35)
        print(f"Teams Cached:        {stats['teams_cached']}")
        print(f"Matches Processed:   {stats['matches_processed']}")
        print(f"Seasons Completed:   {stats['seasons_completed']}")
        
        db_path = "shots_corners_cache.db"
        if os.path.exists(db_path):
            size_bytes = os.path.getsize(db_path)
            size_kb = size_bytes / 1024
            print(f"Database Size:       {size_kb:.1f} KB ({size_bytes} bytes)")
        else:
            print("Database Size:       0 KB (not created yet)")
            
    except Exception as e:
        print(f"❌ Cache error: {e}")


async def show_bookmakers():
    """Show all available bookmakers."""
    try:
        from adapters.odds_api import OddsAPIClient
        
        print("\n🏦 BOOKMAKER DISPONIBILI")
        print("=" * 40)
        print("⏳ Recupero lista bookmaker...")
        
        odds_client = OddsAPIClient()
        bookmakers = await odds_client.get_bookmakers()
        
        if not bookmakers:
            print("❌ Nessun bookmaker trovato")
            return
        
        print(f"\n📋 {len(bookmakers)} bookmaker disponibili:")
        print("-" * 40)
        
        for bookmaker in bookmakers:
            print(f"ID: {bookmaker.get('id', 'N/A'):3d} | {bookmaker.get('name', 'Unknown')}")
        
        print("\n💡 BOOKMAKER PIÙ POPOLARI:")
        print("-" * 30)
        popular_names = ["Bet365", "William Hill", "Betfair", "Unibet", "888sport", "Betway"]
        
        for name in popular_names:
            for bookmaker in bookmakers:
                if name.lower() in bookmaker.get('name', '').lower():
                    print(f"🔥 ID: {bookmaker.get('id'):3d} | {bookmaker.get('name')}")
                    break
        
        print("\n📝 COME USARE:")
        print("Per filtrare le quote per un bookmaker specifico:")
        print("- Usa l'ID del bookmaker nelle chiamate API")
        print("- Esempio: get_fixture_odds(fixture_id, bookmaker_ids=[6])")
        
    except Exception as e:
        print(f"❌ Errore nel recupero bookmaker: {e}")


async def show_available_bets():
    """Show all available betting markets."""
    try:
        from adapters.odds_api import OddsAPIClient
        
        print("\n🎯 MERCATI DI SCOMMESSA DISPONIBILI")
        print("=" * 45)
        print("⏳ Recupero mercati di scommessa...")
        
        odds_client = OddsAPIClient()
        bets = await odds_client.get_available_bets()
        
        if not bets:
            print("❌ Nessun mercato di scommessa trovato")
            return
        
        print(f"\n📋 {len(bets)} mercati disponibili:")
        print("-" * 45)
        
        # Group bets by category
        player_bets = []
        match_bets = []
        other_bets = []
        
        for bet in bets:
            bet_name = str(bet.get('name', '')).lower() if bet.get('name') else ''
            bet_id = str(bet.get('id', 'N/A'))
            bet_display = f"ID: {bet_id:3s} | {bet.get('name', 'Unknown')}"
            
            if any(word in bet_name for word in ['player', 'scorer', 'card', 'booking', 'foul']):
                player_bets.append(bet_display)
            elif any(word in bet_name for word in ['match', 'winner', 'draw', 'over', 'under', 'btts', 'score']):
                match_bets.append(bet_display)
            else:
                other_bets.append(bet_display)
        
        if match_bets:
            print("\n⚽ MERCATI PARTITA:")
            print("-" * 25)
            for bet in match_bets[:15]:  # Show first 15
                print(bet)
            if len(match_bets) > 15:
                print(f"... e altri {len(match_bets) - 15} mercati")
        
        if player_bets:
            print("\n👤 MERCATI GIOCATORI:")
            print("-" * 25)
            for bet in player_bets:
                print(bet)
        
        if other_bets:
            print("\n📊 ALTRI MERCATI:")
            print("-" * 20)
            for bet in other_bets[:10]:  # Show first 10
                print(bet)
            if len(other_bets) > 10:
                print(f"... e altri {len(other_bets) - 10} mercati")
        
        # Search for card-related bets specifically
        card_bets = [bet for bet in bets if any(word in str(bet.get('name', '')).lower() 
                    for word in ['card', 'booking', 'yellow', 'red', 'foul'])]
        
        if card_bets:
            print("\n🟨 MERCATI CARTELLINI SPECIFICI:")
            print("-" * 35)
            for bet in card_bets:
                bet_id = str(bet.get('id', 'N/A'))
                print(f"🎯 ID: {bet_id:>3s} | {bet.get('name', 'Unknown')}")
        
        print("\n💡 COME CERCARE MERCATI SPECIFICI:")
        print("python main.py bets | grep -i 'card'     # Mercati cartellini")
        print("python main.py bets | grep -i 'player'   # Mercati giocatori")
        print("python main.py bets | grep -i 'booking'  # Mercati ammonizioni")
        
    except Exception as e:
        print(f"❌ Errore nel recupero mercati: {e}")


def show_player_database_stats():
    """Show player historical database statistics."""
    try:
        from utils.player_history_db import PlayerHistoryDatabase
        
        print("\n👤 DATABASE GIOCATORI STORICI")
        print("=" * 40)
        
        db = PlayerHistoryDatabase()
        stats = db.get_database_stats()
        
        print(f"📊 Record totali:       {stats['total_records']}")
        print(f"👥 Giocatori unici:     {stats['unique_players']}")
        print(f"📅 Stagioni coperte:    {stats['seasons_covered']}")
        
        # Show some sample historical players
        print(f"\n🏆 TOP GIOCATORI AMMONITI 2024:")
        print("-" * 35)
        
        # Get top carded players from different teams
        teams = ["AS Roma", "Inter", "AC Milan", "Napoli", "Juventus"]
        for team in teams:
            top_players = db.get_team_top_cards(team, 2024, limit=2)
            if top_players:
                print(f"\n⚪ {team}:")
                for player in top_players:
                    print(f"  • {player.player_name}: {player.yellow_cards} cartellini in {player.appearances} partite")
        
        # Show league trends
        league_trends = db.get_league_discipline_trend("Serie A", 2024)
        print(f"\n📈 TENDENZE SERIE A 2024:")
        print("-" * 30)
        print(f"Media cartellini/partita: {league_trends['avg_yellows_per_game']:.2f}")
        print(f"Media falli/partita:      {league_trends['avg_fouls_per_game']:.2f}")
        print(f"Fattore severità:         {league_trends['severity_factor']:.2f}")
        
        print(f"\n💡 UTILIZZO:")
        print("Le previsioni giocatori utilizzano questi dati storici")
        print("per identificare i giocatori più a rischio cartellini.")
        
    except Exception as e:
        print(f"❌ Errore nel database giocatori: {e}")


if __name__ == "__main__":
    main()
