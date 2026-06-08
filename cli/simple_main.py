"""CLI entry point — pure command router, no display logic."""

import asyncio
import sys
from typing import Optional

from core.config import get_settings
from adapters.football_api import FootballAPIError


def main():
    """Dispatch CLI commands."""
    if len(sys.argv) == 1 or sys.argv[1] in ("--help", "-h"):
        _print_help()
        return

    command = sys.argv[1]
    dispatch = {
        "interactive": _cmd_interactive,
        "matchday": _cmd_matchday,
        "config": _cmd_config,
        "cache": _cmd_cache,
        "bookmakers": _cmd_bookmakers,
        "bets": _cmd_bets,
        "players": _cmd_players,
    }
    handler = dispatch.get(command)
    if handler:
        handler()
    else:
        print(f"Unknown command: {command}")
        print("Use 'python main.py --help' for usage information.")


# ── command handlers ──────────────────────────────────────────────────────────

def _cmd_interactive():
    from cli.interactive import run_interactive_menu
    asyncio.run(run_interactive_menu())


def _cmd_matchday():
    league = country = None
    season = None
    i = 2
    while i < len(sys.argv):
        if sys.argv[i] in ("--league", "-l") and i + 1 < len(sys.argv):
            league = sys.argv[i + 1]; i += 2
        elif sys.argv[i] in ("--country", "-c") and i + 1 < len(sys.argv):
            country = sys.argv[i + 1]; i += 2
        elif sys.argv[i] in ("--season", "-s") and i + 1 < len(sys.argv):
            season = int(sys.argv[i + 1]); i += 2
        else:
            i += 1
    asyncio.run(_analyze_matchday(league, country, season))


def _cmd_config():
    try:
        settings = get_settings()
        print("🔧 CURRENT CONFIGURATION")
        print("=" * 30)
        print(f"API Base URL:          {settings.api_football_base}")
        print(f"API Key:               {'*' * (len(settings.api_football_key) - 4)}{settings.api_football_key[-4:]}")
        print(f"Default Country:       {settings.default_country}")
        print(f"Default League:        {settings.default_league}")
        print(f"Default Season:        {settings.default_season}")
        print(f"Primary Bookmaker:     {settings.primary_bookmaker}")
        print(f"Preferred Bookmakers:  {settings.preferred_bookmakers}")
    except Exception as exc:
        print(f"❌ Configuration error: {exc}")


def _cmd_cache():
    try:
        from utils.redis_cache import get_redis_cache
        cache = get_redis_cache()
        print("\n💾 REDIS CACHE STATISTICS")
        print("=" * 35)
        if not cache.is_connected():
            print("❌ Redis non connesso")
            return
        health = cache.health_check()
        mem = health.get("memory_usage", {})
        print(f"Stato:               {health.get('status', 'unknown').upper()}")
        print(f"Chiavi totali:       {mem.get('keys_count', 'N/A')}")
        print(f"Memoria usata:       {mem.get('used_memory_human', 'N/A')} ({mem.get('used_memory_mb', 0):.1f} MB)")
        print(f"Limite memoria:      {mem.get('max_memory_mb', 30)} MB")
        print(f"Utilizzo:            {mem.get('usage_percentage', 0):.1f}%")
    except Exception as exc:
        print(f"❌ Cache error: {exc}")


def _cmd_bookmakers():
    asyncio.run(_show_bookmakers())


def _cmd_bets():
    asyncio.run(_show_available_bets())


def _cmd_players():
    try:
        from utils.redis_cache import get_redis_cache
        cache = get_redis_cache()
        print("\n👤 STATISTICHE GIOCATORI (CACHE REDIS)")
        print("=" * 40)
        if not cache.is_connected():
            print("❌ Redis non connesso")
            return
        settings = get_settings()
        cached_teams = cache.get_cached_teams(settings.default_season)
        print(f"Squadre con dati in cache: {len(cached_teams)}")
        print(f"Stagione:                  {settings.default_season}")
        print()
        print("💡 Usa 'python main.py interactive' per analizzare i giocatori.")
    except Exception as exc:
        print(f"❌ Errore: {exc}")


# ── matchday analysis (coordination only, no display) ────────────────────────

async def _analyze_matchday(
    league: Optional[str], country: Optional[str], season: Optional[int]
):
    try:
        from core.analyzer import MatchAnalyzer
        from cli.match_display import display_matchday

        settings = get_settings()
        analyzer = MatchAnalyzer()

        league_name = league or settings.default_league
        country_name = country or settings.default_country
        season_year = season or settings.default_season

        print(f"⏳ Fetching data for {league_name} ({country_name}) - Season {season_year}...")

        league_id = None
        if league or country:
            league_id = await analyzer.api_client.get_league_id(
                country_name, league_name, season_year
            )

        predictions, round_number = await analyzer.analyze_next_matchday(
            league_id, season_year
        )
        await display_matchday(predictions, league_id, season_year, round_number)

    except FootballAPIError as exc:
        print(f"❌ API Error: {exc}")
    except Exception as exc:
        print(f"❌ Unexpected error: {exc}")


# ── async utility commands ────────────────────────────────────────────────────

async def _show_bookmakers():
    try:
        from adapters.odds_api import OddsAPIClient
        print("\n🏦 BOOKMAKER DISPONIBILI")
        print("=" * 40)
        print("⏳ Recupero lista bookmaker...")
        bookmakers = await OddsAPIClient().get_bookmakers()
        if not bookmakers:
            print("❌ Nessun bookmaker trovato")
            return
        print(f"\n📋 {len(bookmakers)} bookmaker disponibili:")
        print("-" * 40)
        for bm in bookmakers:
            print(f"ID: {bm.get('id', 'N/A'):3d} | {bm.get('name', 'Unknown')}")
        print("\n💡 BOOKMAKER PIÙ POPOLARI:")
        print("-" * 30)
        for name in ("Bet365", "William Hill", "Betfair", "Unibet", "888sport", "Betway"):
            for bm in bookmakers:
                if name.lower() in bm.get("name", "").lower():
                    print(f"🔥 ID: {bm.get('id'):3d} | {bm.get('name')}")
                    break
    except Exception as exc:
        print(f"❌ Errore nel recupero bookmaker: {exc}")


async def _show_available_bets():
    try:
        from adapters.odds_api import OddsAPIClient
        print("\n🎯 MERCATI DI SCOMMESSA DISPONIBILI")
        print("=" * 45)
        bets = await OddsAPIClient().get_available_bets()
        if not bets:
            print("❌ Nessun mercato trovato")
            return

        player_bets, match_bets, other_bets = [], [], []
        for bet in bets:
            name_l = str(bet.get("name", "")).lower()
            bid = str(bet.get("id", "N/A"))
            line = f"ID: {bid:>3s} | {bet.get('name', 'Unknown')}"
            if any(w in name_l for w in ("player", "scorer", "card", "booking", "foul")):
                player_bets.append(line)
            elif any(w in name_l for w in ("match", "winner", "draw", "over", "under", "btts", "score")):
                match_bets.append(line)
            else:
                other_bets.append(line)

        if match_bets:
            print("\n⚽ MERCATI PARTITA:")
            print("-" * 25)
            for b in match_bets[:15]:
                print(b)
            if len(match_bets) > 15:
                print(f"... e altri {len(match_bets) - 15} mercati")

        if player_bets:
            print("\n👤 MERCATI GIOCATORI:")
            print("-" * 25)
            for b in player_bets:
                print(b)

        if other_bets:
            print("\n📊 ALTRI MERCATI:")
            print("-" * 20)
            for b in other_bets[:10]:
                print(b)

        print("\n💡 COME CERCARE MERCATI SPECIFICI:")
        print("python main.py bets | grep -i 'card'")
        print("python main.py bets | grep -i 'player'")
    except Exception as exc:
        print(f"❌ Errore nel recupero mercati: {exc}")


# ── help ──────────────────────────────────────────────────────────────────────

def _print_help():
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
    print("  cache        Mostra statistiche cache Redis")
    print("  bookmakers   Mostra tutti i bookmaker disponibili")
    print("  bets         Mostra tutti i mercati di scommessa disponibili")
    print("  players      Mostra statistiche database giocatori")
    print("")
    print("Options for matchday:")
    print("  --league, -l    League name (e.g., 'Serie A')")
    print("  --country, -c   Country name (e.g., 'Italy')")
    print("  --season, -s    Season year (e.g., 2025)")


if __name__ == "__main__":
    main()
