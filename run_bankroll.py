#!/usr/bin/env python3
"""
Bankroll simulation across leagues.

Starts with a fixed bankroll per league and bets the xG model's value
selections (1X2 + Over/Under 2.5) through a completed season at best-available
odds, reporting the final bankroll.

Usage:
    python run_bankroll.py                       # $100 each on Serie A/Liga/Premier 2025/26
    python run_bankroll.py --season 2024 --edge 0.03
"""

import argparse
import asyncio
import sys

from rich.console import Console
from rich.table import Table

from backtest.ablation import load_seasons
from backtest.xg_data import get_xg_map
from backtest.xg_compare import iter_xg_predictions
from backtest.odds_data import get_league_odds
from backtest.bankroll import build_fuzzy_index, simulate

LEAGUES = [(135, "Serie A"), (140, "La Liga"), (39, "Premier")]


def parse_args():
    p = argparse.ArgumentParser(description="Bankroll simulation")
    p.add_argument("--season", type=int, default=2025)
    p.add_argument("--history", type=str, default="2023,2024")
    p.add_argument("--start", type=float, default=100.0)
    p.add_argument("--edge", type=float, default=0.05)
    p.add_argument("--kelly", type=float, default=0.25)
    p.add_argument("--odds", choices=["sharp", "max"], default="max")
    p.add_argument("--markets", type=str, default="1x2,ou",
                   help="Comma-separated: 1x2, ou")
    return p.parse_args()


async def _xg(league, seasons):
    m = {}
    for s in seasons:
        m.update(await get_xg_map(league, s))
    return m


def main():
    args = parse_args()
    history = [int(s) for s in args.history.split(",") if s.strip()]
    seasons = history + [args.season]

    console = Console()
    table = Table(title=f"SIMULAZIONE BANKROLL — stagione {args.season} · quote {args.odds} "
                        f"· Kelly {args.kelly:g} · edge min {args.edge:+.0%}",
                  header_style="bold cyan")
    table.add_column("Lega")
    table.add_column("Start", justify="right")
    table.add_column("Fine", justify="right")
    table.add_column("Bet", justify="right")
    table.add_column("Vinte", justify="right")
    table.add_column("Yield", justify="right")
    table.add_column("Max DD", justify="right")

    total_start = total_final = 0.0
    for lid, name in LEAGUES:
        try:
            fixtures = load_seasons(lid, seasons)
            xg = asyncio.run(_xg(lid, seasons))
        except FileNotFoundError:
            table.add_row(name, "—", "dati mancanti", "", "", "", "")
            continue
        preds = list(iter_xg_predictions(fixtures, xg, target_season=args.season))
        our_names = {f["home_name"] for f in load_seasons(lid, [args.season])} | \
                    {f["away_name"] for f in load_seasons(lid, [args.season])}
        try:
            odds = get_league_odds(lid, args.season, source=args.odds)
        except Exception as exc:
            table.add_row(name, "—", f"quote ko: {exc}", "", "", "", "")
            continue
        index, unmatched = build_fuzzy_index(odds, our_names)
        sim = simulate(preds, index, start=args.start,
                       edge_threshold=args.edge, kelly_fraction=args.kelly,
                       markets=tuple(m.strip() for m in args.markets.split(",")))

        total_start += args.start
        total_final += sim["final"]
        pstyle = "green" if sim["profit"] >= 0 else "red"
        table.add_row(
            name, f"${args.start:.0f}",
            f"[{pstyle}]${sim['final']:.2f}[/{pstyle}]",
            str(sim["n_bets"]), f"{sim['hit_rate']:.0%}",
            f"[{pstyle}]{sim['yield']:+.1%}[/{pstyle}]",
            f"{sim['max_drawdown']:.0%}",
        )

    console.print()
    console.print(table)
    tstyle = "green" if total_final >= total_start else "red"
    console.print(
        f"\n[bold]TOTALE:[/bold] ${total_start:.0f} → "
        f"[{tstyle}]${total_final:.2f}[/{tstyle}]  "
        f"([{tstyle}]{(total_final-total_start)/total_start:+.1%}[/{tstyle}])\n"
    )
    console.print("[dim]Solo 1X2 + Over/Under 2.5 (unici mercati con quote storiche). "
                  "Cartellini/multigol/BTTS non simulabili (nessuna quota). "
                  "Quote 'max' = migliori disponibili (line-shopping ottimistico).[/dim]\n")


if __name__ == "__main__":
    main()
