"""CLI entry point — minimal command router (config, cache)."""

import argparse
import sys

from cli.deps import build_default_deps
from core.config import get_settings


def main(argv=None):
    """Dispatch CLI commands."""
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("--help", "-h"):
        _print_help()
        return
    command, rest = argv[0], argv[1:]
    if command in ("config", "cache"):
        {"config": _cmd_config, "cache": _cmd_cache}[command]()
    elif command in _LEAN:
        _run_lean(command, rest)
    else:
        print(f"Comando sconosciuto: {command}")
        print("Usa 'python main.py --help' per l'elenco dei comandi.")


_LEAN = ("today", "close", "settle", "report", "players")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="main.py")
    sub = parser.add_subparsers(dest="command")
    today = sub.add_parser("today")
    today.add_argument("--days", type=int, default=3)
    today.add_argument("--dry-run", action="store_true")
    today.add_argument("--bankroll", type=float, default=50.0)
    sub.add_parser("close").add_argument("--minutes", type=int, default=15)
    sub.add_parser("settle")
    sub.add_parser("report").add_argument("--strategy", default=None)
    sub.add_parser("players").add_argument("fixture_id", type=int)
    return parser


def _run_lean(command, rest, deps=None):
    """Run a lean-pipeline command; `deps` is injectable for tests."""
    args = _build_parser().parse_args([command] + rest)
    from cli import commands
    from cli.report_cmd import cmd_report
    try:
        deps = deps or build_default_deps()
    except Exception as exc:
        print(f"Moduli della pipeline non disponibili: {exc}")
        return
    if command == "report":
        cmd_report(deps, args.strategy)
    elif command == "today":
        commands.run(commands.cmd_today(deps, args.days, args.dry_run, args.bankroll))
    elif command == "close":
        commands.run(commands.cmd_close(deps, args.minutes))
    elif command == "settle":
        commands.run(commands.cmd_settle(deps))
    else:
        commands.run(commands.cmd_players(deps, args.fixture_id))


# ── command handlers ──────────────────────────────────────────────────────────

def _cmd_config():
    try:
        settings = get_settings()
        print("🔧 CURRENT CONFIGURATION")
        print("=" * 30)
        print(f"API Base URL:          {settings.api_football_base}")
        print(f"API Key:               {'configured' if settings.api_football_key else 'MISSING'}")
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
        health = cache.health_check()
        backend = health.get("backend", "redis").upper()
        print(f"\n💾 CACHE STATISTICS ({backend})")
        print("=" * 35)
        if not cache.is_connected():
            print(f"❌ Cache {backend} non disponibile")
            return
        mem = health.get("memory_usage", {})
        print(f"Stato:               {health.get('status', 'unknown').upper()}")
        print(f"Chiavi totali:       {mem.get('keys_count', 'N/A')}")
        if backend == "SQLITE":
            stats = health.get("stats", {})
            print(f"File:                {health.get('path', 'N/A')}")
            print(f"Dimensione file:     {mem.get('used_memory_human', 'N/A')} ({mem.get('used_memory_mb', 0):.2f} MB)")
            print(f"Hit / miss:          {stats.get('hits', 0)} / {stats.get('misses', 0)}")
            print(f"Scadute rimosse:     {stats.get('expired', 0)}")
            return
        print(f"Memoria usata:       {mem.get('used_memory_human', 'N/A')} ({mem.get('used_memory_mb', 0):.1f} MB)")
        print(f"Limite memoria:      {mem.get('max_memory_mb', 30)} MB")
        print(f"Utilizzo:            {mem.get('usage_percentage', 0):.1f}%")
    except Exception as exc:
        print(f"❌ Cache error: {exc}")


# ── help ──────────────────────────────────────────────────────────────────────

def _print_help():
    print("Footy Predictor CLI (v2-lean): Serie A, singole in paper trading")
    print("Uso: python main.py <comando> [opzioni]")
    print("")
    print("Comandi:")
    print("  today [--days 3] [--dry-run] [--bankroll 50]  Analisi, singole del giorno e ammoniti")
    print("        esempio: python main.py today --days 2 --dry-run")
    print("  close [--minutes 15]        Salva le quote di chiusura delle partite imminenti")
    print("        esempio: python main.py close --minutes 10")
    print("  settle                      Liquida le partite finite (esito, profitto, CLV)")
    print("  report [--strategy X]       Cassa, ROI, CLV e calibrazione per strategia")
    print("        esempio: python main.py report --strategy raw")
    print("  players <fixture_id>        Candidati ammoniti di una partita")
    print("        esempio: python main.py players 1234567")
    print("  config                      Mostra la configurazione (la chiave API non viene stampata)")
    print("  cache                       Mostra statistiche della cache")
    print("")
    print("Backtest e ricerca: python -m research.<script> --help (cartella research/)")


if __name__ == "__main__":
    main()
