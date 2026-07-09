#!/usr/bin/env python3
"""
Team/match yellow-cards backtest.

Fetches per-match cards (once, cached) and backtests the cards model
(team propensity + referee strictness + shrinkage) on Over 3.5/4.5/5.5 cards,
reporting Brier/skill/calibration and the mean error of expected vs actual.

Usage:
    python run_cards.py                     # Serie A 2024, history 2023
"""

import argparse
import asyncio
import sys

from rich.console import Console
from rich.table import Table

from backtest.ablation import load_seasons
from backtest.cards_data import get_cards_map
from backtest.cards import run_cards_backtest


def parse_args():
    p = argparse.ArgumentParser(description="Team cards backtest")
    p.add_argument("--league", type=int, default=135)
    p.add_argument("--season", type=int, default=2024)
    p.add_argument("--history", type=str, default="2023")
    p.add_argument("--xi", type=float, default=0.0)
    p.add_argument("--refresh-cards", action="store_true")
    return p.parse_args()


async def _merge_cards(league, seasons, refresh):
    merged = {}
    for s in seasons:
        merged.update(await get_cards_map(league, s, refresh=refresh))
    return merged


def main():
    args = parse_args()
    history = [int(s) for s in args.history.split(",") if s.strip()]
    all_seasons = history + [args.season]

    try:
        fixtures = load_seasons(args.league, all_seasons)
    except FileNotFoundError:
        print("❌ Fixtures non in cache:", all_seasons)
        sys.exit(1)

    print(f"📥 Cartellini per lega {args.league}, stagioni {all_seasons}...")
    try:
        cards = asyncio.run(_merge_cards(args.league, all_seasons, args.refresh_cards))
    except Exception as exc:
        print(f"❌ Errore cartellini: {exc}")
        sys.exit(1)

    rep = run_cards_backtest(fixtures, cards, xi=args.xi, score_seasons={args.season})

    console = Console()
    console.print()
    console.rule(f"[bold]CARTELLINI SQUADRA — Lega {args.league} · {args.season} "
                 f"· storico {history}[/bold]")
    console.print(
        f"Partite valutate: [bold]{rep.n}[/bold] · arbitro noto: {rep.ref_coverage:.0%}\n"
        f"Cartellini attesi medi: [bold]{rep.avg_expected}[/bold] vs reali "
        f"[bold]{rep.avg_actual}[/bold] · errore medio (MAE): [bold]{rep.mae}[/bold]\n"
    )

    table = Table(title="Linee Over/Under cartellini", header_style="bold cyan")
    table.add_column("Linea")
    table.add_column("N", justify="right")
    table.add_column("Brier", justify="right")
    table.add_column("Skill", justify="right")
    table.add_column("Prev. media", justify="right")
    table.add_column("Reale", justify="right")
    for r in rep.lines:
        style = "green" if r.brier_skill > 0 else "red"
        table.add_row(
            r.market, str(r.n), f"{r.brier:.3f}",
            f"[{style}]{r.brier_skill:+.3f}[/{style}]",
            f"{r.avg_prediction:.0%}", f"{r.base_rate:.0%}",
        )
    console.print(table)
    console.print("\n[dim]Skill >0 = meglio del prevedere sempre la media. "
                  "MAE = di quanti cartellini sbagliamo in media.[/dim]\n")


if __name__ == "__main__":
    main()
