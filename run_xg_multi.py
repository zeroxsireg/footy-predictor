#!/usr/bin/env python3
"""
Multi-league goals-vs-xG round.

Runs the goals-fed and xG-fed models across the top-5 European leagues for the
two most recent (fully xG-covered) seasons, and consolidates the result into
one table per target season. Fully offline (reads cached fixtures + xG).

Usage:
    python run_xg_multi.py
"""

import asyncio

from rich.console import Console
from rich.table import Table

from backtest.ablation import load_seasons
from backtest.xg_data import get_xg_map
from backtest.xg_compare import run_xg_comparison

LEAGUES = [(135, "Serie A"), (140, "La Liga"), (78, "Bundesliga"),
           (39, "Premier"), (61, "Ligue 1")]
# target season -> history seasons (both well covered for xG)
TARGETS = [(2024, [2023]), (2025, [2024])]


async def _merge_xg(league, seasons):
    merged = {}
    for s in seasons:
        merged.update(await get_xg_map(league, s))
    return merged


def _skill(binary, market):
    return next(b.brier_skill for b in binary if b.market == market)


def _cell(gol_skill, xg_skill):
    better = xg_skill > gol_skill
    style = "green" if xg_skill > 0 else ("yellow" if xg_skill > gol_skill else "red")
    arrow = "→" if abs(xg_skill - gol_skill) > 1e-9 else "="
    mark = "" if better or xg_skill > 0 else ""
    return f"{gol_skill:+.3f}{arrow}[{style}]{xg_skill:+.3f}[/{style}]"


def _rps_cell(gol_rps, xg_rps):
    style = "green" if xg_rps < gol_rps else "red"
    return f"{gol_rps:.4f}→[{style}]{xg_rps:.4f}[/{style}]"


def main():
    console = Console()
    for target, history in TARGETS:
        table = Table(
            title=f"GOL → xG · Brier Skill (verde=xG meglio) · stagione {target} "
                  f"(storico {history})",
            header_style="bold cyan",
        )
        table.add_column("Lega")
        table.add_column("N", justify="right")
        table.add_column("Over 2.5", justify="center")
        table.add_column("Over 3.5", justify="center")
        table.add_column("BTTS", justify="center")
        table.add_column("1X2 (RPS↓)", justify="center")
        table.add_column("xG miss", justify="right")

        for league_id, name in LEAGUES:
            try:
                fixtures = load_seasons(league_id, history + [target])
                xg = asyncio.run(_merge_xg(league_id, history + [target]))
            except FileNotFoundError:
                table.add_row(name, "—", "dati mancanti", "", "", "", "")
                continue
            cmp = run_xg_comparison(fixtures, xg, score_seasons={target})
            gol, xgm = cmp.models["Gol"], cmp.models["xG"]
            table.add_row(
                name, str(cmp.n),
                _cell(_skill(gol.binary, "Over 2.5 Goals"), _skill(xgm.binary, "Over 2.5 Goals")),
                _cell(_skill(gol.binary, "Over 3.5 Goals"), _skill(xgm.binary, "Over 3.5 Goals")),
                _cell(_skill(gol.binary, "BTTS Yes"), _skill(xgm.binary, "BTTS Yes")),
                _rps_cell(gol.result_1x2.rps, xgm.result_1x2.rps),
                str(cmp.xg_missing),
            )
        console.print()
        console.print(table)

    console.print(
        "\n[dim]Skill Brier: >0 = meglio del caso. Verde = xG batte i gol. "
        "1X2 RPS: più basso è meglio (rif. accademico avanzato ~0.195-0.204).[/dim]\n"
    )


if __name__ == "__main__":
    main()
