#!/usr/bin/env python3
"""
Player-level booking backtest ("who gets a yellow?").

Fetches per-match lineups (once, cached) and backtests the player booking model
on Serie A / La Liga, reporting Brier/skill, discrimination (booked vs unbooked)
and ranking quality (precision@k: are the actually-booked players near the top?).

Usage:
    python run_player_cards.py                 # Serie A 2024, history 2023
    python run_player_cards.py --league 140
"""

import argparse
import asyncio
import sys

from rich.console import Console
from rich.table import Table

from backtest.ablation import load_seasons
from backtest.player_data import get_players_map
from backtest.player_cards import run_player_cards_backtest


def parse_args():
    p = argparse.ArgumentParser(description="Player booking backtest")
    p.add_argument("--league", type=int, default=135)
    p.add_argument("--season", type=int, default=2024)
    p.add_argument("--history", type=str, default="2023")
    p.add_argument("--xi", type=float, default=0.0)
    return p.parse_args()


async def _merge_players(league, seasons):
    merged = {}
    for s in seasons:
        merged.update(await get_players_map(league, s))
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

    print(f"📥 Formazioni per lega {args.league}, stagioni {all_seasons}...")
    players = asyncio.run(_merge_players(args.league, all_seasons))

    rep = run_player_cards_backtest(fixtures, players, xi=args.xi, score_seasons={args.season})

    console = Console()
    console.print()
    console.rule(f"[bold]AMMONITI PER GIOCATORE — Lega {args.league} · {args.season}[/bold]")
    console.print(
        f"Coppie (giocatore, partita) valutate: [bold]{rep.n_pairs}[/bold] su {rep.n_matches} partite\n"
        f"Tasso base ammonizione: {rep.base_rate:.1%} per giocatore/partita\n"
    )

    t = Table(header_style="bold cyan", show_header=False)
    t.add_column("Metrica"); t.add_column("Valore", justify="right")
    b = rep.booked
    skill_style = "green" if b.brier_skill > 0 else "red"
    disc_style = "green" if rep.mean_p_booked > rep.mean_p_unbooked else "red"
    t.add_row("Brier / Skill", f"{b.brier:.4f} / [{skill_style}]{b.brier_skill:+.3f}[/{skill_style}]")
    t.add_row("Prob. media — ammoniti vs NON ammoniti",
              f"[{disc_style}]{rep.mean_p_booked:.1%} vs {rep.mean_p_unbooked:.1%}[/{disc_style}]")
    t.add_row("Precision@k (i top-k sono i veri ammoniti?)", f"{rep.precision_at_k:.1%}")
    t.add_row("Ammoniti attesi vs reali per partita", f"{rep.avg_expected} vs {rep.avg_actual}")
    console.print(t)
    console.print(
        "\n[dim]Skill >0 = meglio del caso. Discriminazione buona = prob. ammoniti > non ammoniti. "
        "Precision@k alta = il modello mette i veri ammoniti in cima.[/dim]\n"
    )


if __name__ == "__main__":
    main()
