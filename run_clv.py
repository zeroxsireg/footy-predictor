#!/usr/bin/env python3
"""
CLV test — does the xG model beat the closing market line?

Joins the xG model's value selections with football-data.co.uk closing odds
(Pinnacle preferred) and reports realised ROI, our Brier vs the market's Brier,
and average edge. Positive ROI vs the closing line = a genuine, profitable edge.

Usage:
    python run_clv.py                               # Serie A 2024, history 2023
    python run_clv.py --season 2024 --history 2023 --edge 0.03
"""

import argparse
import asyncio
import sys

from rich.console import Console
from rich.table import Table

from backtest.ablation import load_seasons
from backtest.xg_data import get_xg_map
from backtest.xg_compare import iter_xg_predictions
from backtest.odds_data import get_serie_a_odds, index_by_teams
from backtest.clv import evaluate_clv


def parse_args():
    p = argparse.ArgumentParser(description="CLV test vs closing odds")
    p.add_argument("--league", type=int, default=135)
    p.add_argument("--season", type=int, default=2024)
    p.add_argument("--history", type=str, default="2023")
    p.add_argument("--xi", type=float, default=0.0)
    p.add_argument("--k", type=float, default=5.0)
    p.add_argument("--edge", type=float, default=0.0,
                   help="Minimum EV edge to place a bet (e.g. 0.03 = +3%)")
    p.add_argument("--odds", choices=["sharp", "max"], default="sharp",
                   help="sharp=Pinnacle closing; max=best available (line-shopping)")
    return p.parse_args()


async def _merge_xg(league, seasons):
    merged = {}
    for s in seasons:
        merged.update(await get_xg_map(league, s))
    return merged


def main():
    args = parse_args()
    history = [int(s) for s in args.history.split(",") if s.strip()]
    all_seasons = history + [args.season]

    try:
        fixtures = load_seasons(args.league, all_seasons)
    except FileNotFoundError:
        print("❌ Fixtures non in cache per una delle stagioni:", all_seasons)
        sys.exit(1)

    xg_map = asyncio.run(_merge_xg(args.league, all_seasons))
    predictions = list(iter_xg_predictions(
        fixtures, xg_map, target_season=args.season, xi=args.xi, k=args.k,
    ))

    src_label = "Pinnacle chiusura" if args.odds == "sharp" else "migliori disponibili (line-shopping)"
    print(f"📥 Quote Serie A {args.season} — {src_label} (football-data.co.uk)...")
    try:
        odds = index_by_teams(get_serie_a_odds(args.season, source=args.odds))
    except Exception as exc:
        print(f"❌ Impossibile scaricare le quote: {exc}")
        sys.exit(1)

    report = evaluate_clv(predictions, odds, edge_threshold=args.edge)

    console = Console()
    console.print()
    console.rule(f"[bold]TEST CLV — Serie A {args.season} · quote {args.odds} · "
                 f"soglia edge {args.edge:+.0%}[/bold]")
    console.print(
        f"Partite agganciate alle quote: [bold]{report.matched}[/bold] "
        f"(non agganciate: {report.unmatched})\n"
    )
    if report.unmatched_pairs:
        console.print(f"[yellow]⚠️ Non agganciate: {report.unmatched_pairs[:6]}"
                      f"{'...' if len(report.unmatched_pairs) > 6 else ''}[/yellow]\n")

    table = Table(title="Risultati vs linea di chiusura", header_style="bold cyan")
    table.add_column("Mercato")
    table.add_column("Bet piazzati", justify="right")
    table.add_column("ROI", justify="right")
    table.add_column("Edge medio", justify="right")
    table.add_column("Brier ns / mercato", justify="center")
    for m in report.markets:
        roi_style = "green" if m.roi > 0 else "red"
        beats = "green" if m.our_brier < m.market_brier else "red"
        table.add_row(
            m.market,
            f"{m.n_bets} / {m.n_matches}",
            f"[{roi_style}]{m.roi:+.1%}[/{roi_style}]",
            f"{m.avg_edge:+.1%}",
            f"[{beats}]{m.our_brier:.3f}[/{beats}] / {m.market_brier:.3f}",
        )
    console.print(table)
    console.print(
        "\n[dim]ROI vs la linea di CHIUSURA: >0 = edge reale e profittevole. "
        "Brier: se il nostro < mercato, siamo più calibrati del banco (raro).[/dim]\n"
    )


if __name__ == "__main__":
    main()
