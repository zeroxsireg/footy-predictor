#!/usr/bin/env python3
"""
Goals vs xG backtest.

Fetches per-fixture xG (once, cached) and compares a goals-fed model against an
xG-fed model on the same matches and markets, scored with Brier / Brier-skill
and RPS (for 1X2).

Usage:
    python run_xg.py                       # Serie A 2024/25
    python run_xg.py --league 135 --season 2024 --refresh-xg
"""

import argparse
import asyncio
import sys

from rich.console import Console
from rich.table import Table

from backtest.ablation import load_seasons
from backtest.xg_data import get_xg_map
from backtest.xg_compare import run_xg_comparison


def parse_args():
    p = argparse.ArgumentParser(description="Goals vs xG backtest")
    p.add_argument("--league", type=int, default=135)
    p.add_argument("--season", type=int, default=2024, help="Target season to score")
    p.add_argument("--history", type=str, default="",
                   help="Comma-separated prior seasons for multi-season memory")
    p.add_argument("--xi", type=float, default=0.0, help="Time-decay per day")
    p.add_argument("--k", type=float, default=5.0, help="Shrinkage pseudo-matches")
    p.add_argument("--min-matches", type=int, default=4)
    p.add_argument("--refresh-xg", action="store_true", help="Re-fetch xG from the API")
    return p.parse_args()


async def _merge_xg(league, seasons, refresh):
    merged = {}
    for s in seasons:
        merged.update(await get_xg_map(league, s, refresh=refresh))
    return merged


def main():
    args = parse_args()
    history = [int(s) for s in args.history.split(",") if s.strip()]
    all_seasons = history + [args.season]

    try:
        fixtures = load_seasons(args.league, all_seasons)
    except FileNotFoundError:
        print("❌ Fixtures non in cache. Esegui prima run_backtest.py per ogni stagione: "
              + ", ".join(str(s) for s in all_seasons))
        sys.exit(1)

    print(f"📥 xG per lega {args.league}, stagioni {all_seasons}...")
    try:
        xg_map = asyncio.run(_merge_xg(args.league, all_seasons, args.refresh_xg))
    except Exception as exc:
        print(f"❌ Impossibile ottenere gli xG: {exc}")
        sys.exit(1)

    cmp = run_xg_comparison(
        fixtures, xg_map, xi=args.xi, k=args.k, min_matches=args.min_matches,
        score_seasons={args.season},
    )

    console = Console()
    hist_txt = f" · storico {history}" if history else " · singola stagione"
    console.print()
    console.rule(f"[bold]GOL vs xG — Lega {args.league} · target {args.season}{hist_txt}[/bold]")
    console.print(
        f"Partite valutate: [bold]{cmp.n}[/bold]  "
        f"(xG mancanti, fallback ai gol: {cmp.xg_missing})\n"
    )

    gol, xg = cmp.models["Gol"], cmp.models["xG"]

    table = Table(title="Brier Skill per mercato — verde=meglio del caso; ⭐=modello migliore",
                  header_style="bold cyan")
    table.add_column("Mercato")
    table.add_column("Gol (Skill / Brier)", justify="center")
    table.add_column("xG (Skill / Brier)", justify="center")

    def cell(r, win):
        style = "green" if r.brier_skill > 0 else "red"
        star = "⭐ " if win else "   "
        return f"{star}[{style}]{r.brier_skill:+.3f}[/{style}] [dim]({r.brier:.3f})[/dim]"

    for gb, xb in zip(gol.binary, xg.binary):
        xg_wins = xb.brier_skill > gb.brier_skill
        table.add_row(gb.market, cell(gb, not xg_wins), cell(xb, xg_wins))

    # 1X2 row (Brier + RPS; lower is better)
    g1, x1 = gol.result_1x2, xg.result_1x2
    xg_1x2_wins = x1.rps < g1.rps
    table.add_row(
        "Risultato 1X2 [dim](RPS / Brier ↓)[/dim]",
        f"{'   ' if xg_1x2_wins else '⭐ '}{g1.rps:.4f} [dim]/ {g1.brier:.3f}[/dim]",
        f"{'⭐ ' if xg_1x2_wins else '   '}{x1.rps:.4f} [dim]/ {x1.brier:.3f}[/dim]",
    )
    console.print(table)
    console.print(
        "\n[dim]Stessa architettura, stesse partite: l'unica differenza è "
        "l'input (gol reali vs xG). RPS/Brier più bassi = meglio.[/dim]\n"
    )


if __name__ == "__main__":
    main()
