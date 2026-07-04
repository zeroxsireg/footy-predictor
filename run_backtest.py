#!/usr/bin/env python3
"""
Level-1 accuracy backtest CLI.

Replays a completed season and measures how well the model predicts
(Brier score, hit-rate, calibration) — no betting odds involved.

Usage:
    python run_backtest.py                    # Serie A 2025/26, from cache
    python run_backtest.py --refresh          # force a fresh API download
    python run_backtest.py --league 39 --season 2024 --min-matches 5

The season data is fetched from the API only once (a single bulk call) and
cached under backtest/data/; every later run is fully offline.
"""

import argparse
import asyncio
import os
import sys

from backtest.data import get_season_fixtures, cache_path
from backtest.runner import run_backtest
from backtest.report import print_report


def parse_args():
    p = argparse.ArgumentParser(description="Footy Predictor — Level 1 backtest")
    p.add_argument("--league", type=int, default=135, help="API league id (135 = Serie A)")
    p.add_argument("--season", type=int, default=2025, help="Season start year (2025 = 2025/26)")
    p.add_argument("--min-matches", type=int, default=4,
                   help="Skip predictions until both teams have played this many games")
    p.add_argument("--refresh", action="store_true", help="Re-download from the API even if cached")
    return p.parse_args()


async def _load(league: int, season: int, refresh: bool):
    path = cache_path(league, season)
    if refresh or not os.path.exists(path):
        print(f"⏳ Scarico le partite dall'API (lega {league}, stagione {season})...")
    else:
        print(f"📂 Uso i dati in cache: {path}")
    return await get_season_fixtures(league, season, refresh=refresh)


def main():
    args = parse_args()
    try:
        fixtures = asyncio.run(_load(args.league, args.season, args.refresh))
    except Exception as exc:
        print(f"❌ Impossibile ottenere i dati: {exc}")
        print("   Suggerimento: verifica API_FOOTBALL_KEY in .env, o usa una cache esistente.")
        sys.exit(1)

    finished = [f for f in fixtures if f.get("status") == "FT"]
    print(f"✅ {len(fixtures)} partite totali, {len(finished)} concluse (FT).\n")

    if not finished:
        print("❌ Nessuna partita conclusa: stagione non ancora giocata o dati vuoti.")
        sys.exit(1)

    report = run_backtest(
        fixtures, league_id=args.league, season=args.season, min_matches=args.min_matches
    )
    print_report(report)


if __name__ == "__main__":
    main()
