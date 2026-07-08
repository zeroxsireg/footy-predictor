#!/usr/bin/env python3
"""
Advanced 1X2 ablation — the "free squeeze".

Measures whether the research's non-xG techniques (multi-season history,
time-decay, shrinkage, global home advantage) improve the 1X2 forecast,
scored with RPS (primary), Brier and accuracy. Fully offline: reads the
cached season data produced by run_backtest.py.

Usage:
    python run_advanced.py                         # Serie A 2024, history 2022+2023
    python run_advanced.py --league 39 --target-season 2024 --history 2023

Requires the relevant seasons already cached (run run_backtest.py for each first).
"""

import argparse
import sys

from rich.console import Console
from rich.table import Table

from backtest.ablation import run_ablation


def parse_args():
    p = argparse.ArgumentParser(description="Advanced 1X2 ablation (free squeeze)")
    p.add_argument("--league", type=int, default=135)
    p.add_argument("--target-season", type=int, default=2024)
    p.add_argument("--history", type=str, default="2022,2023",
                   help="Comma-separated prior seasons to use as history")
    p.add_argument("--k", type=float, default=5.0, help="Shrinkage pseudo-matches")
    return p.parse_args()


def main():
    args = parse_args()
    history = [int(s) for s in args.history.split(",") if s.strip()]
    xi_grid = [0.001, 0.002, 0.003, 0.005, 0.008]

    try:
        results = run_ablation(
            league_id=args.league,
            target_season=args.target_season,
            history_seasons=history,
            xi_grid=xi_grid,
            k=args.k,
        )
    except FileNotFoundError as exc:
        print(f"❌ Dati mancanti in cache: {exc}")
        print("   Esegui prima:  python run_backtest.py --league "
              f"{args.league} --season <anno>  per ogni stagione richiesta.")
        sys.exit(1)

    console = Console()
    console.print()
    console.rule(
        f"[bold]ABLATION 1X2 — Lega {args.league} · target {args.target_season} "
        f"· storico {history}[/bold]"
    )
    console.print(
        f"Partite valutate: [bold]{results[0].n}[/bold] (stesse per tutte le config)\n"
    )

    best_rps = min(r.rps for r in results)
    table = Table(title="Configurazioni  —  RPS più basso è meglio", header_style="bold cyan")
    table.add_column("Configurazione")
    table.add_column("RPS", justify="right")
    table.add_column("Brier", justify="right")
    table.add_column("Accuratezza", justify="right")
    for r in results:
        star = "⭐ " if r.rps == best_rps else "  "
        rps_style = "green" if r.rps == best_rps else "white"
        table.add_row(
            star + r.label,
            f"[{rps_style}]{r.rps:.4f}[/{rps_style}]",
            f"{r.brier:.4f}",
            f"{r.accuracy:.1%}",
        )
    console.print(table)
    console.print(
        "\n[dim]RPS: standard aureo per l'1X2 (penalizza per distanza ordinale). "
        "Riferimenti ricerca: baseline ~0.24, modelli avanzati ~0.195-0.204.[/dim]\n"
    )


if __name__ == "__main__":
    main()
