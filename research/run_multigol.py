#!/usr/bin/env python3
"""
Multigol backtest (derived from the xG model, no extra data).

Usage:
    python run_multigol.py                     # Serie A 2024, history 2023
    python run_multigol.py --league 140
"""

import argparse
import asyncio
import sys

from rich.console import Console
from rich.table import Table

from backtest.ablation import load_seasons
from backtest.xg_data import get_xg_map
from backtest.multigol import run_multigol_backtest


def parse_args():
    p = argparse.ArgumentParser(description="Multigol backtest")
    p.add_argument("--league", type=int, default=135)
    p.add_argument("--season", type=int, default=2024)
    p.add_argument("--history", type=str, default="2023")
    p.add_argument("--k", type=float, default=5.0)
    return p.parse_args()


async def _merge_xg(league, seasons):
    m = {}
    for s in seasons:
        m.update(await get_xg_map(league, s))
    return m


def main():
    args = parse_args()
    history = [int(s) for s in args.history.split(",") if s.strip()]
    all_seasons = history + [args.season]
    try:
        fixtures = load_seasons(args.league, all_seasons)
    except FileNotFoundError:
        print("❌ Fixtures non in cache:", all_seasons)
        sys.exit(1)

    xg = asyncio.run(_merge_xg(args.league, all_seasons))
    n, results = run_multigol_backtest(fixtures, xg, target_season=args.season, k=args.k)

    console = Console()
    console.print()
    console.rule(f"[bold]MULTIGOL — Lega {args.league} · {args.season} · storico {history}[/bold]")
    console.print(f"Partite valutate: [bold]{n}[/bold]\n")

    table = Table(header_style="bold cyan")
    table.add_column("Mercato")
    table.add_column("Brier", justify="right")
    table.add_column("Skill", justify="right")
    table.add_column("Prev. media", justify="right")
    table.add_column("Reale", justify="right")
    for r in results:
        style = "green" if r.brier_skill > 0 else "red"
        gap = abs(r.avg_prediction - r.base_rate)
        cal = "green" if gap <= 0.03 else "yellow" if gap <= 0.06 else "red"
        table.add_row(
            r.market, f"{r.brier:.3f}",
            f"[{style}]{r.brier_skill:+.3f}[/{style}]",
            f"[{cal}]{r.avg_prediction:.0%}[/{cal}]", f"{r.base_rate:.0%}",
        )
    console.print(table)
    console.print("\n[dim]Skill >0 = meglio del caso. Prev.media ≈ Reale = ben calibrato.[/dim]\n")


if __name__ == "__main__":
    main()
