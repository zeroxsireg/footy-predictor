#!/usr/bin/env python3
"""
Forward prediction — predict a match as if it hasn't been played yet.

Uses only data available before the match (as-of cutoff), so it demonstrates
exactly how the product will work live once the season starts. Off-season demo:
picks a real past match, predicts it forward, then reveals what happened.

Usage:
    python predict_upcoming.py                          # Serie A: Napoli vs Juventus
    python predict_upcoming.py --home Roma --away Lazio
    python predict_upcoming.py --league 140 --home Barcelona --away "Real Madrid"
"""

import argparse
import sys

from rich.console import Console

from backtest.ablation import load_seasons
from backtest.card import predict_upcoming, find_fixture_id
from backtest.card_render import render_card
from backtest.cards_data import cards_cache_path, load_cards_map
from backtest.player_data import players_cache_path, load_players_map


def parse_args():
    p = argparse.ArgumentParser(description="Forward prediction")
    p.add_argument("--league", type=int, default=135)
    p.add_argument("--season", type=int, default=2024)
    p.add_argument("--history", type=str, default="2023")
    p.add_argument("--home", type=str, default="Napoli")
    p.add_argument("--away", type=str, default="Juventus")
    return p.parse_args()


def _actual(league, season, home, away):
    """Find the real fixture (date + result) for the demo comparison."""
    fid = find_fixture_id(league, season, home, away)
    if fid is None:
        return None, None
    fx = next(f for f in load_seasons(league, [season]) if f["fixture_id"] == fid)
    actual = {"home_goals": fx.get("home_goals"), "away_goals": fx.get("away_goals")}
    try:
        cm = load_cards_map(cards_cache_path(league, season)).get(str(fid))
        if cm:
            actual["total_cards"] = (cm.get("home_cards") or 0) + (cm.get("away_cards") or 0)
    except FileNotFoundError:
        pass
    try:
        roster = load_players_map(players_cache_path(league, season)).get(str(fid)) or []
        actual["booked"] = [p["name"] for p in roster if (p.get("yellow") or 0) >= 1]
    except FileNotFoundError:
        pass
    return fx["date"], actual


def main():
    args = parse_args()
    history = [int(s) for s in args.history.split(",") if s.strip()]

    as_of, actual = _actual(args.league, args.season, args.home, args.away)
    if as_of is None:
        print(f"❌ Partita non trovata: {args.home} vs {args.away}")
        sys.exit(1)

    card = predict_upcoming(
        args.league, args.home, args.away,
        season=args.season, history_seasons=history, as_of_date=as_of,
    )
    if not card:
        print("❌ Pronostico non generabile.")
        sys.exit(1)

    console = Console()
    console.print("[dim]Pronostico generato al momento PRE-partita, coi soli dati "
                  "precedenti (come farà il prodotto in diretta).[/dim]")
    render_card(console, card, actual=actual)


if __name__ == "__main__":
    main()
