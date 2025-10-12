"""
Daily League Analysis CLI Module

Handles the command-line interface for daily league analysis including:
- League selection
- Analysis execution
- Results display
"""

import asyncio
from typing import Optional, Tuple

from core.config import get_settings
from core.daily_analyzer import DailyLeagueAnalyzer
from cli.daily_display import DailyAnalysisDisplayer
from adapters.football_api import FootballAPIClient
from config.leagues import get_league_manager


class DailyLeagueAnalysisCLI:
    """CLI interface for daily league analysis."""
    
    def __init__(self):
        self.analyzer = DailyLeagueAnalyzer()
        self.displayer = DailyAnalysisDisplayer()
        self.league_manager = get_league_manager()
        
        # Build available leagues from enabled leagues (excluding cups)
        self.available_leagues = {}
        idx = 1
        for league in self.league_manager.get_enabled_leagues():
            if not league.is_cup:
                self.available_leagues[str(idx)] = (
                    league.country, 
                    league.name, 
                    league.flag, 
                    league.country  # country_it (for display)
                )
                idx += 1
        
        # Add "ALL" option for national leagues
        self.available_leagues[str(idx)] = ("ALL", "Tutti i campionati", "🌍", "Tutti")
        idx += 1
        
        # Build available cups from enabled leagues (only cups)
        self.available_cups = {}
        for league in self.league_manager.get_enabled_leagues():
            if league.is_cup:
                self.available_cups[str(idx)] = (
                    league.country,
                    league.name,
                    league.flag,
                    league.country  # country_it (for display)
                )
                idx += 1
        
        # Add "ALL" option for cups
        self.available_cups[str(idx)] = ("ALL", "Tutte le coppe", "🏆🥈", "Tutte")
    
    async def run(self):
        """Run the daily league analysis CLI."""
        while True:
            try:
                print("\n🏆 ANALISI GIORNATA COMPLETA")
                print("=" * 50)
                
                # Step 1: Select league
                league_info = self._select_league()
                if not league_info:
                    return
                
                country, league_name, flag, country_it = league_info
                
                # Handle special cases for "ALL" selections
                if country == "ALL":
                    if league_name == "Tutti i campionati":
                        await self._run_all_leagues_analysis()
                    elif league_name == "Tutte le coppe":
                        await self._run_all_cups_analysis()
                    # Continue loop for "ALL" selections
                    continue
                
                # Step 2: Confirm analysis for single league/cup
                if not self._confirm_analysis(league_name, flag, country_it):
                    continue
                
                # Step 3: Run analysis
                print(f"\n⏳ Avvio analisi per {flag} {country_it} {league_name}...")
                print("⏱️  Questa operazione potrebbe richiedere alcuni minuti...")
                
                analysis = await self.analyzer.analyze_league_matchday(
                    country=country,
                    league_name=league_name,
                    country_flag=flag,
                    country_it=country_it,
                    season=2025
                )
                
                # Step 4: Display results
                self.displayer.display_daily_analysis(analysis)
                
                # Step 5: Offer to save results
                self._offer_save_results(analysis)
                
                # Step 6: Ask if user wants to continue
                print("\n" + "="*50)
                continue_choice = input("🔄 Vuoi fare un'altra analisi? (s/n): ").strip().lower()
                if continue_choice not in ['s', 'si', 'y', 'yes']:
                    print("👋 Arrivederci!")
                    break
                
            except KeyboardInterrupt:
                print("\n\n⚠️ Analisi interrotta dall'utente")
                break
            except Exception as e:
                print(f"\n❌ Errore durante l'analisi: {e}")
                print("💡 Suggerimento: Verifica la connessione internet e riprova")
                
                # Ask if user wants to retry
                retry_choice = input("🔄 Vuoi riprovare? (s/n): ").strip().lower()
                if retry_choice not in ['s', 'si', 'y', 'yes']:
                    break
    
    def _select_league(self) -> Optional[Tuple[str, str, str, str]]:
        """Display league selection menu and return selected league info."""
        
        print("\n📋 SELEZIONA CAMPIONATO PER ANALISI GIORNATA:")
        print("-" * 50)
        
        # Campionati nazionali
        print("🏆 CAMPIONATI NAZIONALI:")
        for key, (country, league, flag, country_it) in self.available_leagues.items():
            print(f"{key}. {flag} {country_it} - {league}")
        
        print("\n🏅 COPPE EUROPEE:")
        for key, (country, league, flag, country_it) in self.available_cups.items():
            print(f"{key}. {flag} {league}")
        
        print("\n0. Torna al menu principale")
        
        while True:
            try:
                choice = input(f"\n🎯 Scegli un campionato (1-9, 0 per tornare): ").strip()
                
                if choice == "0":
                    return None
                
                # Check in leagues first, then cups
                if choice in self.available_leagues:
                    return self.available_leagues[choice]
                elif choice in self.available_cups:
                    return self.available_cups[choice]
                else:
                    print("❌ Scelta non valida. Riprova.")
                    
            except (ValueError, KeyboardInterrupt):
                print("\n👋 Operazione annullata")
                return None
    
    def _confirm_analysis(self, league_name: str, flag: str, country_it: str) -> bool:
        """Ask user to confirm the analysis."""
        
        print(f"\n⚠️  CONFERMA ANALISI")
        print("-" * 30)
        print(f"📊 Campionato: {flag} {country_it} {league_name}")
        print(f"⏱️  Tempo stimato: 2-5 minuti")
        print(f"📡 Operazioni: Analisi di tutte le partite della giornata")
        print(f"🎯 Output: Top picks + combinazioni ottimali")
        
        while True:
            try:
                confirm = input(f"\n🚀 Procedere con l'analisi? (s/n): ").strip().lower()
                
                if confirm in ['s', 'si', 'y', 'yes']:
                    return True
                elif confirm in ['n', 'no']:
                    print("❌ Analisi annullata")
                    return False
                else:
                    print("❌ Risposta non valida. Usa 's' per sì o 'n' per no.")
                    
            except KeyboardInterrupt:
                print("\n❌ Analisi annullata")
                return False
    
    def _offer_save_results(self, analysis):
        """Offer to save analysis results to file."""
        
        print(f"\n💾 SALVATAGGIO RISULTATI")
        print("-" * 30)
        print("💡 Vuoi salvare i risultati dell'analisi in un file?")
        print("📄 Formato: Testo leggibile con tutti i picks e combinazioni")
        
        while True:
            try:
                save_choice = input(f"\n💾 Salvare i risultati? (s/n): ").strip().lower()
                
                if save_choice in ['s', 'si', 'y', 'yes']:
                    self._save_results_to_file(analysis)
                    break
                elif save_choice in ['n', 'no']:
                    print("📄 Risultati non salvati")
                    break
                else:
                    print("❌ Risposta non valida. Usa 's' per sì o 'n' per no.")
                    
            except KeyboardInterrupt:
                print("\n📄 Operazione di salvataggio annullata")
                break
    
    def _save_results_to_file(self, analysis):
        """Save analysis results to a text file."""
        
        try:
            # Generate filename
            timestamp = analysis.analysis_date.strftime("%Y%m%d_%H%M%S")
            league_safe = analysis.league_name.replace(" ", "_").replace("UEFA_", "")
            filename = f"daily_analysis_{league_safe}_{timestamp}.txt"
            
            # Create content
            content = self._generate_file_content(analysis)
            
            # Write file
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(content)
            
            print(f"✅ Risultati salvati in: {filename}")
            
        except Exception as e:
            print(f"❌ Errore nel salvataggio: {e}")
    
    def _generate_file_content(self, analysis) -> str:
        """Generate text content for file save."""
        
        lines = []
        lines.append("🏆 FOOTY PREDICTOR - ANALISI GIORNATA COMPLETA")
        lines.append("=" * 60)
        lines.append(f"📅 Campionato: {analysis.league_name}")
        lines.append(f"📊 Giornata: {analysis.matchday}")
        lines.append(f"📈 Partite analizzate: {analysis.matches_analyzed}")
        lines.append(f"🎯 Picks totali: {analysis.total_picks}")
        lines.append(f"⏰ Data analisi: {analysis.analysis_date.strftime('%d/%m/%Y %H:%M')}")
        lines.append("")
        
        # Summary
        lines.append("📈 RIEPILOGO STATISTICHE:")
        lines.append(f"   🔥 High Confidence: {analysis.summary['high_confidence_picks']}")
        lines.append(f"   ⚡ Medium Confidence: {analysis.summary['medium_confidence_picks']}")
        lines.append(f"   📊 Confidenza media: {analysis.summary['average_confidence']:.1f}%")
        lines.append("")
        
        # Top picks
        lines.append(f"🥇 TOP {len(analysis.top_picks)} PICKS:")
        lines.append("-" * 40)
        for i, pick in enumerate(analysis.top_picks, 1):
            confidence_emoji = "🔥" if pick.confidence == "HIGH" else "⚡"
            time_str = pick.match_time.strftime("%H:%M")
            lines.append(f"{i:2d}. {confidence_emoji} {pick.home_team} vs {pick.away_team}")
            lines.append(f"    ⏰ {time_str} │ {pick.market}: {pick.selection}")
            lines.append(f"    💰 {pick.odds_range} │ {pick.percentage:.1f}%")
            lines.append(f"    💬 {pick.reasoning}")
            lines.append("")
        
        # Combinations
        if analysis.combinations:
            lines.append("🎯 COMBINAZIONI OTTIMALI:")
            lines.append("-" * 30)
            for i, combo in enumerate(analysis.combinations, 1):
                risk_emoji = {"LOW": "🟢", "MEDIUM": "🟡", "HIGH": "🔴"}.get(combo.get("risk_level", "MEDIUM"), "⚪")
                lines.append(f"{i}. {risk_emoji} {combo.get('description', 'Combinazione')}")
                lines.append(f"   📊 Confidenza: {combo.get('confidence', 0):.1f}%")
                lines.append(f"   💰 Odds stimate: {combo.get('estimated_odds', 0):.1f}")
                lines.append("")
        
        return "\n".join(lines)
    
    async def _run_all_leagues_analysis(self):
        """Run analysis for all national leagues."""
        print("\n🌍 ANALISI TUTTI I CAMPIONATI NAZIONALI")
        print("=" * 50)
        print("⚠️  Questa operazione analizzerà tutti i 5 campionati principali")
        print("⏱️  Tempo stimato: 5-10 minuti")
        
        confirm = input("\n🎯 Confermi l'analisi completa? (s/n): ").strip().lower()
        if confirm not in ['s', 'si', 'y', 'yes']:
            print("❌ Analisi annullata")
            return
        
        # Get all enabled national leagues (excluding cups)
        all_leagues = [
            (league.country, league.name, league.flag, league.country)
            for league in self.league_manager.get_enabled_leagues()
            if not league.is_cup
        ]
        
        all_analyses = []
        
        for country, league_name, flag, country_it in all_leagues:
            print(f"\n📊 Analizzando {flag} {country_it} - {league_name}...")
            try:
                analysis = await self.analyzer.analyze_league_matchday(
                    country=country,
                    league_name=league_name,
                    country_flag=flag,
                    country_it=country_it,
                    season=2025
                )
                if analysis:
                    all_analyses.append(analysis)
                    print(f"✅ Completato: {analysis.total_matches_analyzed} partite, {analysis.total_picks_generated} picks")
                else:
                    print(f"⚠️ Nessuna partita trovata per {league_name}")
            except Exception as e:
                print(f"❌ Errore per {league_name}: {e}")
        
        # Display combined results
        if all_analyses:
            print(f"\n🎉 ANALISI COMPLETA COMPLETATA!")
            print(f"📊 {len(all_analyses)} campionati analizzati")
            total_matches = sum(a.total_matches_analyzed for a in all_analyses)
            total_picks = sum(a.total_picks_generated for a in all_analyses)
            print(f"⚽ {total_matches} partite totali")
            print(f"🎯 {total_picks} picks totali")
            
            # Show summary for each league
            for analysis in all_analyses:
                print(f"\n{analysis.country_flag} {analysis.league_name}:")
                print(f"   ⚽ {analysis.total_matches_analyzed} partite")
                print(f"   🎯 {analysis.total_picks_generated} picks")
                print(f"   📊 Confidenza media: {analysis.summary_stats.get('average_confidence', 0):.1f}%")
            
            # Automatically show detailed analysis for each league
            print(f"\n📋 ANALISI DETTAGLIATA PER OGNI CAMPIONATO")
            print("-" * 50)
            
            try:
                for analysis in all_analyses:
                    print(f"\n{'='*80}")
                    print(f"🏆 ANALISI DETTAGLIATA - {analysis.country_flag} {analysis.league_name}")
                    print(f"{'='*80}")
                    self.displayer.display_daily_analysis(analysis)
                    
                    # Ask if user wants to continue or stop
                    if analysis != all_analyses[-1]:  # Not the last one
                        continue_choice = input(f"\n⏭️ Continuare con il prossimo campionato? (s/n): ").strip().lower()
                        if continue_choice not in ['s', 'si', 'y', 'yes']:
                            break
                        
            except KeyboardInterrupt:
                print("\n⚠️ Visualizzazione interrotta dall'utente")
            
            # Advanced menu after analysis completion
            await self._show_advanced_menu(all_analyses)
                
        else:
            print("❌ Nessuna analisi completata con successo")
    
    async def _run_all_cups_analysis(self):
        """Run analysis for all European cups."""
        print("\n🏆 ANALISI TUTTE LE COPPE EUROPEE")
        print("=" * 50)
        print("⚠️  Questa operazione analizzerà Champions League e Europa League")
        print("⏱️  Tempo stimato: 3-5 minuti")
        
        confirm = input("\n🎯 Confermi l'analisi completa? (s/n): ").strip().lower()
        if confirm not in ['s', 'si', 'y', 'yes']:
            print("❌ Analisi annullata")
            return
        
        # Get all enabled European cups
        all_cups = [
            (league.country, league.name, league.flag, league.country)
            for league in self.league_manager.get_enabled_leagues()
            if league.is_cup
        ]
        
        all_analyses = []
        
        for country, league_name, flag, country_it in all_cups:
            print(f"\n📊 Analizzando {flag} {league_name}...")
            try:
                analysis = await self.analyzer.analyze_league_matchday(
                    country=country,
                    league_name=league_name,
                    country_flag=flag,
                    country_it=country_it,
                    season=2025
                )
                if analysis:
                    all_analyses.append(analysis)
                    print(f"✅ Completato: {analysis.total_matches_analyzed} partite, {analysis.total_picks_generated} picks")
                else:
                    print(f"⚠️ Nessuna partita trovata per {league_name}")
            except Exception as e:
                print(f"❌ Errore per {league_name}: {e}")
        
        # Display combined results
        if all_analyses:
            print(f"\n🎉 ANALISI COMPLETA COMPLETATA!")
            print(f"🏆 {len(all_analyses)} coppe analizzate")
            total_matches = sum(a.total_matches_analyzed for a in all_analyses)
            total_picks = sum(a.total_picks_generated for a in all_analyses)
            print(f"⚽ {total_matches} partite totali")
            print(f"🎯 {total_picks} picks totali")
            
            # Show summary for each cup
            for analysis in all_analyses:
                print(f"\n{analysis.country_flag} {analysis.league_name}:")
                print(f"   ⚽ {analysis.total_matches_analyzed} partite")
                print(f"   🎯 {analysis.total_picks_generated} picks")
                print(f"   📊 Confidenza media: {analysis.summary_stats.get('average_confidence', 0):.1f}%")
            
            # Automatically show detailed analysis for each cup
            print(f"\n📋 ANALISI DETTAGLIATA PER OGNI COPPA")
            print("-" * 50)
            
            try:
                for analysis in all_analyses:
                    print(f"\n{'='*80}")
                    print(f"🏆 ANALISI DETTAGLIATA - {analysis.country_flag} {analysis.league_name}")
                    print(f"{'='*80}")
                    self.displayer.display_daily_analysis(analysis)
                    
                    # Ask if user wants to continue or stop
                    if analysis != all_analyses[-1]:  # Not the last one
                        continue_choice = input(f"\n⏭️ Continuare con la prossima coppa? (s/n): ").strip().lower()
                        if continue_choice not in ['s', 'si', 'y', 'yes']:
                            break
                        
            except KeyboardInterrupt:
                print("\n⚠️ Visualizzazione interrotta dall'utente")
            
            # Advanced menu after analysis completion
            await self._show_advanced_menu(all_analyses)
                
        else:
            print("❌ Nessuna analisi completata con successo")
    
    async def _show_advanced_menu(self, all_analyses):
        """Show advanced menu after completing all analyses."""
        if not all_analyses:
            return
            
        print(f"\n{'='*60}")
        print("🎯 COSA VUOI FARE ADESSO?")
        print("="*60)
        print("1. 🔄 Fare un'altra analisi")
        print("2. 📅 Filtrare per giorno del match")
        print("3. 🏷️  Filtrare migliori picks per categoria")
        print("0. 🚪 Uscire")
        
        while True:
            try:
                choice = input(f"\n🎯 Scegli un'opzione (0-3): ").strip()
                
                if choice == "0":
                    print("👋 Arrivederci!")
                    return
                elif choice == "1":
                    print("🔄 Tornando al menu principale...")
                    return
                elif choice == "2":
                    await self._filter_by_match_day(all_analyses)
                    # Continue loop to show menu again
                elif choice == "3":
                    await self._filter_by_category(all_analyses)
                    # Continue loop to show menu again
                else:
                    print("❌ Opzione non valida. Scegli 0-3.")
                    
            except KeyboardInterrupt:
                print("\n👋 Arrivederci!")
                return
    
    async def _filter_by_match_day(self, all_analyses):
        """Filter picks by match day."""
        print(f"\n📅 FILTRO PER GIORNO DEL MATCH")
        print("="*50)
        
        # Collect all regular picks with their match days (excluding player cards picks)
        all_picks = []
        for analysis in all_analyses:
            # Regular picks only (no player cards picks)
            for pick in analysis.top_picks:
                match_day = pick.match_time.strftime("%A")  # Day of week
                match_date = pick.match_time.strftime("%d/%m/%Y")
                all_picks.append({
                    'pick': pick,
                    'day': match_day,
                    'date': match_date,
                    'league': analysis.league_name,
                    'flag': analysis.country_flag
                })
        
        if not all_picks:
            print("❌ Nessun pick disponibile per il filtraggio")
            return
        
        # Get unique days with their datetime objects for sorting
        unique_days = {}
        for pick_data in all_picks:
            pick = pick_data['pick']
            day = pick_data['day']
            date = pick_data['date']
            if day not in unique_days:
                unique_days[day] = {
                    'date': date,
                    'datetime': pick.match_time
                }
        
        # Sort days by date (chronological order)
        sorted_days = sorted(unique_days.items(), key=lambda x: x[1]['datetime'])
        
        # Show available days
        print("📅 GIORNI DISPONIBILI:")
        day_options = {}
        for i, (day, day_info) in enumerate(sorted_days, 1):
            day_options[str(i)] = day
            print(f"{i}. {day} ({day_info['date']})")
        
        print("0. Torna indietro")
        
        # Get user choice
        while True:
            try:
                choice = input(f"\n🎯 Scegli un giorno (0-{len(sorted_days)}): ").strip()
                
                if choice == "0":
                    return
                elif choice in day_options:
                    selected_day = day_options[choice]
                    await self._show_picks_for_day(all_picks, selected_day, all_analyses)
                    return  # Return to advanced menu
                else:
                    print(f"❌ Opzione non valida. Scegli 0-{len(sorted_days)}.")
                    
            except KeyboardInterrupt:
                return
    
    async def _show_picks_for_day(self, all_picks, selected_day, all_analyses):
        """Show all picks for a specific day."""
        # Filter picks for the selected day (all_picks now contains only regular picks)
        day_picks = [p for p in all_picks if p['day'] == selected_day]
        
        if not day_picks:
            print(f"❌ Nessun pick regolare trovato per {selected_day}")
            # Still try to show player cards if available
            await self._show_player_cards_for_day(all_analyses, selected_day)
            return
        
        # Sort by confidence
        day_picks.sort(key=lambda x: x['pick'].confidence_score, reverse=True)
        
        print(f"\n🏆 MIGLIORI PICKS PER {selected_day.upper()}")
        print("="*70)
        print(f"📊 Trovati {len(day_picks)} picks regolari")
        
        for i, pick_data in enumerate(day_picks, 1):
            pick = pick_data['pick']
            league = pick_data['league']
            flag = pick_data['flag']
            
            print(f"\n{i:2d}. 🔥 {pick.home_team} vs {pick.away_team}")
            print(f"    {flag} {league} │ ⏰ {pick.match_time.strftime('%H:%M')}")
            print(f"    {pick.market}: {pick.selection}")
            print(f"    💰 {pick.odds_range} │ {pick.confidence} {pick.percentage:.1f}%")
            print(f"    💬 {pick.reasoning}")
        
        # Add player cards picks for this day
        await self._show_player_cards_for_day(all_analyses, selected_day)
        
        # Ask if user wants to continue
        print(f"\n{'='*50}")
        continue_choice = input("🔄 Tornare al menu avanzato? (s/n): ").strip().lower()
        if continue_choice not in ['s', 'si', 'y', 'yes']:
            print("👋 Arrivederci!")
            return
    
    async def _show_player_cards_for_day(self, all_analyses, selected_day):
        """Show top 8 player cards picks for a specific day."""
        # Collect all player cards picks for this day from all analyses
        day_player_cards = []
        
        for analysis in all_analyses:
            if analysis.top_player_cards_picks:
                for pick in analysis.top_player_cards_picks:
                    match_day = pick.match_time.strftime("%A")
                    if match_day == selected_day:
                        day_player_cards.append({
                            'pick': pick,
                            'league': analysis.league_name,
                            'flag': analysis.country_flag
                        })
        
        if not day_player_cards:
            return
        
        # Sort by confidence score
        day_player_cards.sort(key=lambda x: x['pick'].confidence_score, reverse=True)
        
        # Take top 8
        top_8_player_cards = day_player_cards[:8]
        
        print(f"\n🟨 TOP {len(top_8_player_cards)} PICKS AMMONITI (GIOCATORI) PER {selected_day.upper()}:")
        print("="*70)
        
        for i, pick_data in enumerate(top_8_player_cards, 1):
            pick = pick_data['pick']
            league = pick_data['league']
            flag = pick_data['flag']
            
            # Extract player name from market field (format: "Player Card - {player_name}")
            player_name = "Unknown Player"
            if "Player Card - " in pick.market:
                player_name = pick.market.replace("Player Card - ", "")
            
            # Get team name from player_team field
            team_name = pick.player_team or "Unknown Team"
            
            # Format confidence emoji
            if pick.confidence_score >= 70:
                confidence_emoji = "🔥"
            elif pick.confidence_score >= 50:
                confidence_emoji = "⚡"
            else:
                confidence_emoji = "💡"
            
            print(f"{i:2d}. {confidence_emoji} {player_name} ({team_name})")
            print(f"    🏟️ {pick.home_team} vs {pick.away_team} ⏰ {pick.match_time.strftime('%H:%M')} │ 📅 {pick.match_time.strftime('%d/%m/%Y')} - {pick.match_time.strftime('%A')}")
            print(f"    {flag} {league}")
            print(f"    🟨 {pick.selection} │ 💰 {pick.odds_range}")
            print(f"    📊 {pick.confidence_score:.1f}% │ 💬 {pick.reasoning}")
            print()
    
    async def _filter_by_category(self, all_analyses):
        """Filter picks by category."""
        print(f"\n🏷️  FILTRO PER CATEGORIA")
        print("="*50)
        
        # Collect all picks with their categories
        all_picks = []
        for analysis in all_analyses:
            for pick in analysis.top_picks:
                category = self._get_pick_category(pick)
                all_picks.append({
                    'pick': pick,
                    'category': category,
                    'league': analysis.league_name,
                    'flag': analysis.country_flag
                })
        
        if not all_picks:
            print("❌ Nessun pick disponibile per il filtraggio")
            return
        
        # Get unique categories
        unique_categories = set(p['category'] for p in all_picks)
        
        # Show available categories
        print("🏷️  CATEGORIE DISPONIBILI:")
        category_options = {}
        for i, category in enumerate(sorted(unique_categories), 1):
            category_options[str(i)] = category
            print(f"{i}. {category}")
        
        print("0. Torna indietro")
        
        # Get user choice
        while True:
            try:
                choice = input(f"\n🎯 Scegli una categoria (0-{len(unique_categories)}): ").strip()
                
                if choice == "0":
                    return
                elif choice in category_options:
                    selected_category = category_options[choice]
                    await self._show_picks_for_category(all_picks, selected_category)
                    return  # Return to advanced menu
                else:
                    print(f"❌ Opzione non valida. Scegli 0-{len(unique_categories)}.")
                    
            except KeyboardInterrupt:
                return
    
    async def _show_picks_for_category(self, all_picks, selected_category):
        """Show all picks for a specific category."""
        category_picks = [p for p in all_picks if p['category'] == selected_category]
        
        if not category_picks:
            print(f"❌ Nessun pick trovato per {selected_category}")
            return
        
        # Sort by confidence
        category_picks.sort(key=lambda x: x['pick'].confidence_score, reverse=True)
        
        print(f"\n🏆 MIGLIORI PICKS PER {selected_category.upper()}")
        print("="*70)
        print(f"📊 Trovati {len(category_picks)} picks")
        
        for i, pick_data in enumerate(category_picks, 1):
            pick = pick_data['pick']
            league = pick_data['league']
            flag = pick_data['flag']
            
            print(f"\n{i:2d}. 🔥 {pick.home_team} vs {pick.away_team}")
            print(f"    {flag} {league} │ ⏰ {pick.match_time.strftime('%H:%M')}")
            print(f"    {pick.market}: {pick.selection}")
            print(f"    💰 {pick.odds_range} │ {pick.confidence} {pick.percentage:.1f}%")
            print(f"    💬 {pick.reasoning}")
        
        # Ask if user wants to continue
        print(f"\n{'='*50}")
        continue_choice = input("🔄 Tornare al menu avanzato? (s/n): ").strip().lower()
        if continue_choice not in ['s', 'si', 'y', 'yes']:
            print("👋 Arrivederci!")
            return
    
    def _get_pick_category(self, pick):
        """Get category name for a pick."""
        market = pick.market.lower()
        
        if 'btts' in market or 'both teams' in market:
            return "Both Teams to Score"
        elif 'cards' in market:
            return "Cards"
        elif 'goals' in market and 'match' in market:
            return "Match Goals"
        elif 'goals' in market:
            return "Team Goals"
        elif 'result' in market or 'match result' in market:
            return "Match Result"
        elif 'shots' in market:
            return "Shots"
        elif 'corners' in market:
            return "Corners"
        else:
            return "Other"


async def run_daily_league_analysis():
    """Entry point for daily league analysis."""
    cli = DailyLeagueAnalysisCLI()
    await cli.run()
