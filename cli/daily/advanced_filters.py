"""
Advanced post-analysis filters for daily matchday analysis.

Allows filtering picks by match day, category, and showing top player cards.
"""

from typing import List, Dict, Any


class DailyAdvancedFilters:
    """Handles advanced filtering menus and drill-downs for daily picks."""

    @staticmethod
    def get_pick_category(pick) -> str:
        """Get category name for a pick."""
        market = pick.market.lower()
        if "btts" in market or "both teams" in market:
            return "Both Teams to Score"
        elif "cards" in market:
            return "Cards"
        elif "goals" in market and "match" in market:
            return "Match Goals"
        elif "goals" in market:
            return "Team Goals"
        elif "result" in market or "match result" in market:
            return "Match Result"
        elif "shots" in market:
            return "Shots"
        elif "corners" in market:
            return "Corners"
        else:
            return "Other"

    @classmethod
    async def show_advanced_menu(cls, all_analyses):
        """Show advanced menu after completing all analyses."""
        if not all_analyses:
            return

        print(f"\n{'='*60}")
        print("🎯 COSA VUOI FARE ADESSO?")
        print("=" * 60)
        print("1. 🔄 Fare un'altra analisi")
        print("2. 📅 Filtrare per giorno del match")
        print("3. 🏷️  Filtrare migliori picks per categoria")
        print("0. 🚪 Uscire")

        while True:
            try:
                choice = input("\n🎯 Scegli un'opzione (0-3): ").strip()
                if choice == "0":
                    print("👋 Arrivederci!")
                    return
                elif choice == "1":
                    print("🔄 Tornando al menu principale...")
                    return
                elif choice == "2":
                    await cls.filter_by_match_day(all_analyses)
                elif choice == "3":
                    await cls.filter_by_category(all_analyses)
                else:
                    print("❌ Opzione non valida. Scegli 0-3.")
            except KeyboardInterrupt:
                print("\n👋 Arrivederci!")
                return

    @classmethod
    async def filter_by_match_day(cls, all_analyses):
        """Filter picks by match day."""
        print(f"\n📅 FILTRO PER GIORNO DEL MATCH")
        print("=" * 50)

        all_picks = []
        for analysis in all_analyses:
            for pick in analysis.top_picks:
                all_picks.append({
                    "pick": pick,
                    "day": pick.match_time.strftime("%A"),
                    "date": pick.match_time.strftime("%d/%m/%Y"),
                    "league": analysis.league_name,
                    "flag": analysis.country_flag,
                })

        if not all_picks:
            print("❌ Nessun pick disponibile per il filtraggio")
            return

        unique_days = {}
        for pick_data in all_picks:
            day = pick_data["day"]
            if day not in unique_days:
                unique_days[day] = {
                    "date": pick_data["date"],
                    "datetime": pick_data["pick"].match_time,
                }

        sorted_days = sorted(unique_days.items(), key=lambda x: x[1]["datetime"])
        print("📅 GIORNI DISPONIBILI:")
        day_options = {}
        for i, (day, day_info) in enumerate(sorted_days, 1):
            day_options[str(i)] = day
            print(f"{i}. {day} ({day_info['date']})")
        print("0. Torna indietro")

        while True:
            try:
                choice = input(f"\n🎯 Scegli un giorno (0-{len(sorted_days)}): ").strip()
                if choice == "0":
                    return
                elif choice in day_options:
                    selected_day = day_options[choice]
                    await cls.show_picks_for_day(all_picks, selected_day, all_analyses)
                    return
                else:
                    print(f"❌ Opzione non valida. Scegli 0-{len(sorted_days)}.")
            except KeyboardInterrupt:
                return

    @classmethod
    async def show_picks_for_day(cls, all_picks, selected_day, all_analyses):
        """Show all picks for a specific day."""
        day_picks = [p for p in all_picks if p["day"] == selected_day]
        if not day_picks:
            print(f"❌ Nessun pick regolare trovato per {selected_day}")
            await cls.show_player_cards_for_day(all_analyses, selected_day)
            return

        day_picks.sort(key=lambda x: x["pick"].confidence_score, reverse=True)
        print(f"\n🏆 MIGLIORI PICKS PER {selected_day.upper()}")
        print("=" * 70)
        print(f"📊 Trovati {len(day_picks)} picks regolari")

        for i, pick_data in enumerate(day_picks, 1):
            pick = pick_data["pick"]
            print(f"\n{i:2d}. 🔥 {pick.home_team} vs {pick.away_team}")
            print(f"    {pick_data['flag']} {pick_data['league']} │ ⏰ {pick.match_time.strftime('%H:%M')}")
            print(f"    {pick.market}: {pick.selection}")
            print(f"    💰 {pick.odds_range} │ {pick.confidence} {pick.percentage:.1f}%")
            print(f"    💬 {pick.reasoning}")

        await cls.show_player_cards_for_day(all_analyses, selected_day)
        print(f"\n{'='*50}")
        continue_choice = input("🔄 Tornare al menu avanzato? (s/n): ").strip().lower()
        if continue_choice not in ["s", "si", "y", "yes"]:
            print("👋 Arrivederci!")

    @classmethod
    async def show_player_cards_for_day(cls, all_analyses, selected_day):
        """Show top 8 player cards picks for a specific day."""
        day_player_cards = []
        for analysis in all_analyses:
            if analysis.top_player_cards_picks:
                for pick in analysis.top_player_cards_picks:
                    if pick.match_time.strftime("%A") == selected_day:
                        day_player_cards.append({
                            "pick": pick,
                            "league": analysis.league_name,
                            "flag": analysis.country_flag,
                        })

        if not day_player_cards:
            return

        day_player_cards.sort(key=lambda x: x["pick"].confidence_score, reverse=True)
        top_8_player_cards = day_player_cards[:8]

        print(f"\n🟨 TOP {len(top_8_player_cards)} PICKS AMMONITI (GIOCATORI) PER {selected_day.upper()}:")
        print("=" * 70)

        for i, pick_data in enumerate(top_8_player_cards, 1):
            pick = pick_data["pick"]
            player_name = (
                pick.market.replace("Player Card - ", "")
                if "Player Card - " in pick.market
                else "Unknown Player"
            )
            team_name = pick.player_team or "Unknown Team"
            emoji = "🔥" if pick.confidence_score >= 70 else ("⚡" if pick.confidence_score >= 50 else "💡")

            print(f"{i:2d}. {emoji} {player_name} ({team_name})")
            print(f"    🏟️ {pick.home_team} vs {pick.away_team} ⏰ {pick.match_time.strftime('%H:%M')} │ 📅 {pick.match_time.strftime('%d/%m/%Y')} - {pick.match_time.strftime('%A')}")
            print(f"    {pick_data['flag']} {pick_data['league']}")
            print(f"    🟨 {pick.selection} │ 💰 {pick.odds_range}")
            print(f"    📊 {pick.confidence_score:.1f}% │ 💬 {pick.reasoning}\n")

    @classmethod
    async def filter_by_category(cls, all_analyses):
        """Filter picks by category."""
        print(f"\n🏷️  FILTRO PER CATEGORIA")
        print("=" * 50)

        all_picks = []
        for analysis in all_analyses:
            for pick in analysis.top_picks:
                all_picks.append({
                    "pick": pick,
                    "category": cls.get_pick_category(pick),
                    "league": analysis.league_name,
                    "flag": analysis.country_flag,
                })

        if not all_picks:
            print("❌ Nessun pick disponibile per il filtraggio")
            return

        unique_categories = sorted(set(p["category"] for p in all_picks))
        print("🏷️  CATEGORIE DISPONIBILI:")
        category_options = {}
        for i, category in enumerate(unique_categories, 1):
            category_options[str(i)] = category
            print(f"{i}. {category}")
        print("0. Torna indietro")

        while True:
            try:
                choice = input(f"\n🎯 Scegli una categoria (0-{len(unique_categories)}): ").strip()
                if choice == "0":
                    return
                elif choice in category_options:
                    selected_category = category_options[choice]
                    await cls.show_picks_for_category(all_picks, selected_category)
                    return
                else:
                    print(f"❌ Opzione non valida. Scegli 0-{len(unique_categories)}.")
            except KeyboardInterrupt:
                return

    @classmethod
    async def show_picks_for_category(cls, all_picks, selected_category):
        """Show all picks for a specific category."""
        category_picks = [p for p in all_picks if p["category"] == selected_category]
        if not category_picks:
            print(f"❌ Nessun pick trovato per {selected_category}")
            return

        category_picks.sort(key=lambda x: x["pick"].confidence_score, reverse=True)
        print(f"\n🏆 MIGLIORI PICKS PER {selected_category.upper()}")
        print("=" * 70)
        print(f"📊 Trovati {len(category_picks)} picks")

        for i, pick_data in enumerate(category_picks, 1):
            pick = pick_data["pick"]
            print(f"\n{i:2d}. 🔥 {pick.home_team} vs {pick.away_team}")
            print(f"    {pick_data['flag']} {pick_data['league']} │ ⏰ {pick.match_time.strftime('%H:%M')}")
            print(f"    {pick.market}: {pick.selection}")
            print(f"    💰 {pick.odds_range} │ {pick.confidence} {pick.percentage:.1f}%")
            print(f"    💬 {pick.reasoning}")

        print(f"\n{'='*50}")
        continue_choice = input("🔄 Tornare al menu avanzato? (s/n): ").strip().lower()
        if continue_choice not in ["s", "si", "y", "yes"]:
            print("👋 Arrivederci!")
