"""Main menu for choosing between live, pre-match, and daily league analysis."""

import asyncio
from cli.interactive import InteractiveMenu
from cli.live_analysis import run_live_analysis
from cli.daily_analysis import run_daily_league_analysis
from cli.utility_menu import UtilityMenuCLI


async def run_main_menu():
    """Run the main menu for choosing analysis type."""
    print("🏆 FOOTY PREDICTOR - ANALISI INTERATTIVA")
    print("=" * 50)
    
    while True:
        # Ask for analysis type
        print("\n📊 TIPO DI ANALISI:")
        print("-" * 25)
        print("1. 🔴 LIVE - Partite in corso")
        print("2. ⏰ PRE-MATCH - Prossime partite")
        print("3. 🏆 DAILY - Analisi giornaliera campionato")
        print("4. 🔧 UTILITY - Gestione dati e cache")
        print("0. Esci")
        
        try:
            analysis_choice = input("\n🎯 Scegli il tipo di analisi (1-4, 0 per uscire): ").strip()
            
            if analysis_choice == "0":
                print("👋 Arrivederci!")
                break
            elif analysis_choice == "1":
                # Live analysis
                print("\n🔴 MODALITÀ LIVE ATTIVATA")
                print("=" * 30)
                await run_live_analysis()
            elif analysis_choice == "2":
                # Pre-match analysis (existing functionality)
                print("\n⏰ MODALITÀ PRE-MATCH ATTIVATA")
                print("=" * 35)
                menu = InteractiveMenu()
                await menu.run_prematch_menu()
            elif analysis_choice == "3":
                # Daily league analysis (new functionality)
                print("\n🏆 MODALITÀ ANALISI GIORNATA ATTIVATA")
                print("=" * 40)
                await run_daily_league_analysis()
            elif analysis_choice == "4":
                # Utility menu for data management
                print("\n🔧 MODALITÀ UTILITY ATTIVATA")
                print("=" * 35)
                utility_menu = UtilityMenuCLI()
                await utility_menu.run()
            else:
                print("❌ Scelta non valida. Riprova.")
                continue
                
            # Ask if user wants to continue
            print("\n" + "=" * 50)
            continue_choice = input("🔄 Vuoi fare un'altra analisi? (s/n): ").strip().lower()
            if continue_choice not in ['s', 'si', 'y', 'yes']:
                print("👋 Arrivederci!")
                break
                
        except KeyboardInterrupt:
            print("\n👋 Arrivederci!")
            break
        except Exception as e:
            print(f"❌ Errore: {e}")
            continue
