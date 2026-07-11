#!/usr/bin/env python3
"""
Multi-league validation of the team cards model.

Runs the cards backtest across the top-5 leagues (target 2024, history 2023) and
consolidates Brier skill per Over line plus the expected-vs-actual calibration,
to confirm the positive skill seen on Serie A is robust. Fully offline.

Usage:
    python run_cards_multi.py
"""

import asyncio

from rich.console import Console
from rich.table import Table

from backtest.ablation import load_seasons
from backtest.cards_data import get_cards_map
from backtest.cards import run_cards_backtest, LINES

LEAGUES = [(135, "Serie A"), (140, "La Liga"), (78, "Bundesliga"),
           (39, "Premier")]
TARGET, HISTORY = 2024, [2023]


async def _merge_cards(league, seasons):
    merged = {}
    for s in seasons:
        merged.update(await get_cards_map(league, s))
    return merged


def main():
    console = Console()
    table = Table(
        title=f"MODELLO CARTELLINI — Brier Skill per lega (target {TARGET}, storico {HISTORY})",
        header_style="bold cyan",
    )
    table.add_column("Lega")
    table.add_column("N", justify="right")
    for ln in LINES:
        table.add_column(f"Over {ln}", justify="center")
    table.add_column("Attesi/Reali", justify="center")
    table.add_column("Arb.", justify="right")

    for lid, name in LEAGUES:
        try:
            fx = load_seasons(lid, HISTORY + [TARGET])
            cards = asyncio.run(_merge_cards(lid, HISTORY + [TARGET]))
        except FileNotFoundError:
            table.add_row(name, "—", *["dati mancanti"] + [""] * (len(LINES)), "", "")
            continue
        rep = run_cards_backtest(fx, cards, score_seasons={TARGET})
        cells = []
        for line in rep.lines:
            style = "green" if line.brier_skill > 0 else "red"
            cells.append(f"[{style}]{line.brier_skill:+.3f}[/{style}]")
        table.add_row(
            name, str(rep.n), *cells,
            f"{rep.avg_expected}/{rep.avg_actual}",
            f"{rep.ref_coverage:.0%}",
        )

    console.print()
    console.print(table)
    console.print(
        "\n[dim]Skill >0 (verde) = meglio del prevedere sempre la media. "
        "Attesi/Reali = calibrazione (più vicini è meglio).[/dim]\n"
    )


if __name__ == "__main__":
    main()
