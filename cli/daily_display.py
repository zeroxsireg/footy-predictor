"""
Daily League Analysis Display Module

Handles the display of daily league analysis results including:
- Top picks ranking
- Optimal combinations
- Summary statistics
"""

from typing import List
from datetime import datetime
from rich.console import Console

from core.daily_analyzer import DailyLeagueAnalysis, DailyPick, BettingCombination


class DailyAnalysisDisplayer:
    """Displays daily league analysis results in a formatted way."""
    
    def __init__(self):
        self.console = Console()
    
    def display_daily_analysis(self, analysis: DailyLeagueAnalysis):
        """Display complete daily league analysis."""
        
        # Header
        print(f"\n🏆 ANALISI GIORNATA COMPLETA - {analysis.league_name.upper()}")
        print("═" * 70)
        
        # Basic info
        print(f"📅 Giornata: {analysis.round_number}")
        print(f"📊 Partite analizzate: {analysis.total_matches_analyzed}")
        print(f"🎯 Picks totali generati: {analysis.total_picks_generated}")
        print(f"⏰ Analisi completata: {analysis.analysis_timestamp.strftime('%d/%m/%Y %H:%M')}")
        
        # Summary stats
        print(f"\n📈 RIEPILOGO STATISTICHE:")
        print(f"   🔥 High Confidence: {analysis.summary_stats['high_confidence_picks']}")
        print(f"   ⚡ Medium Confidence: {analysis.summary_stats['medium_confidence_picks']}")
        print(f"   📊 Confidenza media: {analysis.summary_stats['average_confidence']:.1f}%")
        
        # Top picks
        self._display_top_picks(analysis.top_picks)
        
        # Combinations
        self._display_combinations(analysis.optimal_combinations)
        
        # Final summary
        self._display_final_summary(analysis)
        
        # Display individual player cards picks
        self._display_top_cards_picks(analysis)
    
    def _display_top_picks(self, top_picks: List[DailyPick]):
        """Display top individual picks grouped by match."""
        
        print(f"\n🥇 TUTTI I {len(top_picks)} PICKS (RAGGRUPPATI PER PARTITA):")
        print("─" * 70)
        
        # Group picks by match
        matches = {}
        for pick in top_picks:
            match_key = f"{pick.home_team} vs {pick.away_team}"
            if match_key not in matches:
                matches[match_key] = []
            matches[match_key].append(pick)
        
        # ORDINA LE PARTITE CRONOLOGICAMENTE (per data/ora)
        sorted_matches = sorted(matches.items(), key=lambda x: x[1][0].match_time)
        
        # Display picks grouped by match (in ordine cronologico)
        match_number = 1
        for match_key, match_picks in sorted_matches:
            # Sort picks by percentage within each match (highest first)
            match_picks.sort(key=lambda p: p.percentage, reverse=True)
            
            # Match header - COLORATO con data/ora sulla stessa riga
            time_str = match_picks[0].match_time.strftime("%H:%M")
            date_str = match_picks[0].match_time.strftime("%d/%m/%Y")
            day_str = match_picks[0].match_time.strftime("%A")
            
            # Traduci giorno in italiano
            day_translations = {
                "Monday": "Lunedì", "Tuesday": "Martedì", "Wednesday": "Mercoledì",
                "Thursday": "Giovedì", "Friday": "Venerdì", "Saturday": "Sabato", "Sunday": "Domenica"
            }
            day_str = day_translations.get(day_str, day_str)
            
            print(f"\n\033[1;36m{match_number}. 🏟️  {match_key}\033[0m  │  \033[1;33m📅 {day_str} {date_str} ⏰ {time_str}\033[0m")
            print("─" * 90)
            
            # Display all picks for this match
            for i, pick in enumerate(match_picks, 1):
                # Confidence emoji (nuovo sistema unificato)
                confidence_emoji = "🔥" if pick.confidence == "HIGH" else "⚡" if pick.confidence == "MEDIUM" else "⚠️"
                
                # Probability emoji (nuovo sistema)
                if pick.percentage >= 75:
                    prob_emoji = "✅"
                elif pick.percentage >= 60:
                    prob_emoji = "📊"
                else:
                    prob_emoji = "❗"
                
                # COLORA IL PICK (verde per evidenziarlo)
                print(f"   \033[1;32mPick {i}:\033[0m {confidence_emoji} \033[1;37m{pick.market}: {pick.selection}\033[0m")
                
                # Mostra quote reali se disponibili
                if pick.real_odds and pick.bookmaker:
                    odds_color = "\033[1;33m"  # Giallo per quote reali
                    print(f"           💎 {odds_color}Quota: {pick.real_odds:.2f}\033[0m ({pick.bookmaker}) • {prob_emoji} {pick.percentage:.1f}%")
                else:
                    print(f"           {prob_emoji} {pick.percentage:.1f}% • ❌ Quote non disponibili")
                
                print(f"           💬 {pick.reasoning}")
            
            match_number += 1
        
        print()
    
    def _display_combinations(self, combinations: List[BettingCombination]):
        """Display betting combinations."""
        
        if not combinations:
            print("\n⚠️ Nessuna combinazione ottimale disponibile")
            return
        
        print(f"\n🎯 COMBINAZIONI OTTIMALI ({len(combinations)} disponibili):")
        print("─" * 70)
        
        for i, combo in enumerate(combinations, 1):
            # Risk level emoji
            risk_emoji = {
                "LOW": "🟢",
                "MEDIUM": "🟡", 
                "HIGH": "🔴"
            }.get(combo.get("risk_level", "MEDIUM"), "⚪")
            
            print(f"{i}. {risk_emoji} {combo.get('description', 'Combinazione')}")
            print(f"   📊 Confidenza: {combo.get('confidence', 0):.1f}% │ 💰 Odds stimate: {combo.get('estimated_odds', 0):.1f}")
            print(f"   🎯 Picks ({len(combo.get('picks', []))}):")
            
            # Show individual picks in combination
            for j, pick in enumerate(combo.get('picks', []), 1):
                confidence_emoji = "🔥" if pick.confidence == "HIGH" else "⚡"
                print(f"      {j}. {confidence_emoji} {pick.home_team} vs {pick.away_team}")
                print(f"         {pick.market}: {pick.selection} ({pick.percentage:.1f}%)")
            
            print()
    
    def _display_final_summary(self, analysis: DailyLeagueAnalysis):
        """Display final analysis summary."""
        
        print("\n" + "═" * 70)
        print("📋 RIEPILOGO FINALE")
        print("═" * 70)
        
        # Best picks by category
        self._display_best_by_category(analysis.top_picks)
        
        # Recommended strategy
        self._display_strategy_recommendation(analysis)
        
        print(f"\n✨ Analisi completata con successo!")
        print(f"🎯 {analysis.summary_stats['high_confidence_picks']} picks ad alta confidenza disponibili")
        print(f"🏆 {len(analysis.optimal_combinations)} combinazioni ottimali generate")
    
    def _display_best_by_category(self, top_picks: List[DailyPick]):
        """Display best picks by category."""
        
        print("\n🏅 MIGLIORI PICKS PER CATEGORIA:")
        
        # Group by market category
        categories = {}
        for pick in top_picks[:10]:  # Top 10 only
            if "Goals" in pick.market:
                category = "⚽ Goals"
            elif "Both Teams" in pick.market:
                category = "🤝 BTTS"
            elif "Shots" in pick.market:
                category = "🏹 Shots"
            elif "Corners" in pick.market:
                category = "📐 Corners"
            elif "Cards" in pick.market:
                category = "🟨 Cards"
            else:
                category = "📊 Altri"
            
            if category not in categories:
                categories[category] = []
            categories[category].append(pick)
        
        # Display best from each category
        for category, picks in categories.items():
            best_pick = max(picks, key=lambda p: p.confidence_score)
            confidence_emoji = "🔥" if best_pick.confidence == "HIGH" else "⚡"
            
            # Format match name
            match_name = f"{best_pick.home_team} vs {best_pick.away_team}"
            
            print(f"   {category}: {confidence_emoji} {best_pick.selection} ({best_pick.percentage:.1f}%)")
            print(f"      📍 {match_name}")
        
        # Special section for Top 4 Cards picks
        # Note: We need to pass the analysis object, but this method is called from _display_best_by_category
        # For now, we'll skip the player cards display here and handle it in the main display method
    
    def _display_top_cards_picks(self, analysis: DailyLeagueAnalysis):
        """Display top 8 individual player cards picks with detailed analysis."""
        if not analysis.top_player_cards_picks:
            return
        
        print(f"\n🟨 TOP 8 PICKS AMMONITI (GIOCATORI):")
        print("=" * 60)
        
        # Italian day names
        days_italian = {
            'Monday': 'Lunedì', 'Tuesday': 'Martedì', 'Wednesday': 'Mercoledì',
            'Thursday': 'Giovedì', 'Friday': 'Venerdì', 'Saturday': 'Sabato', 'Sunday': 'Domenica'
        }
        
        for i, pick in enumerate(analysis.top_player_cards_picks, 1):
            confidence_emoji = "🔥" if pick.confidence == "HIGH" else "⚡" if pick.confidence == "MEDIUM" else "💡"
            
            # Format match name with time
            match_name = f"{pick.home_team} vs {pick.away_team} ⏰ {pick.match_time.strftime('%H:%M')}"
            
            # Extract player name from market
            player_name = pick.market.replace("Player Card - ", "")
            
            # Get player team from the pick data
            player_team = pick.player_team
            
            # Format date with day of week
            day_english = pick.match_time.strftime('%A')
            day_italian = days_italian.get(day_english, day_english)
            date_formatted = f"{pick.match_time.strftime('%d/%m/%Y')} - {day_italian}"
            
            # Quote rimosse - da riprogrammare
            odds_display = pick.real_odds if pick.real_odds else "N/A"
            bookmaker_info = f" ({pick.bookmaker})" if pick.bookmaker else ""
            
            # Use Rich console for proper formatting
            if player_team:
                self.console.print(f" {i}. {confidence_emoji} [bold]{player_name}[/bold] ([dim]{player_team}[/dim])")
            else:
                self.console.print(f" {i}. {confidence_emoji} [bold]{player_name}[/bold]")
            
            # All match info on one line
            self.console.print(f"    🏟️ {match_name} │ 📅 {date_formatted}")
            self.console.print(f"    🟨 {pick.selection} │ 💰 {odds_display}{bookmaker_info}")
            self.console.print(f"    📊 [bold]{pick.percentage:.1f}%[/bold] │ 💬 [dim]{pick.reasoning}[/dim]")
            self.console.print()
    
    def _display_strategy_recommendation(self, analysis: DailyLeagueAnalysis):
        """Display betting strategy recommendation."""
        
        high_count = analysis.summary_stats['high_confidence_picks']
        combo_count = len(analysis.optimal_combinations)
        
        print(f"\n💡 STRATEGIA RACCOMANDATA:")
        
        if high_count >= 5 and combo_count >= 2:
            print("   🎯 APPROCCIO CONSERVATORE: Usa le combinazioni 3-4 picks")
            print("   💰 APPROCCIO AGRESSIVO: Prova la combinazione 5 picks")
            print("   ⚖️ BILANCIATO: Mix di singoli picks + combinazioni")
        elif high_count >= 3:
            print("   🎯 FOCUS: Concentrati sui singoli picks high-confidence")
            print("   💰 OPPORTUNITÀ: Usa la combinazione disponibile con cautela")
        else:
            print("   ⚠️ CAUTELA: Pochi picks ad alta confidenza disponibili")
            print("   📊 STRATEGIA: Focus su picks individuali più sicuri")
    
    def _get_percentage_color(self, percentage: float) -> str:
        """Get color emoji for percentage."""
        if percentage >= 75:
            return "🔴"
        elif percentage >= 60:
            return "🟠"
        elif percentage >= 50:
            return "🟡"
        else:
            return "🟢"
