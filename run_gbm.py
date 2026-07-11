#!/usr/bin/env python3
"""
GBM vs parametric model.

Builds point-in-time features across the top-5 leagues, trains a gradient
boosting model on 2023+2024 and tests out-of-sample on 2025, comparing it head
to head with the parametric xG model on Over 2.5, BTTS and 1X2.

Usage:
    python run_gbm.py                       # pooled top-5, train 23+24, test 25
"""

import argparse
import asyncio
import sys

import pandas as pd
from rich.console import Console
from rich.table import Table

from backtest.ablation import load_seasons
from backtest.xg_data import get_xg_map
from backtest.features import build_feature_frame
from backtest.gbm import train_and_evaluate

LEAGUES = [(135, "Serie A"), (140, "La Liga"), (78, "Bundesliga"),
           (39, "Premier")]


def parse_args():
    p = argparse.ArgumentParser(description="GBM vs parametric")
    p.add_argument("--seasons", type=str, default="2023,2024,2025")
    p.add_argument("--test-season", type=int, default=2025)
    p.add_argument("--xi", type=float, default=0.0)
    p.add_argument("--k", type=float, default=5.0)
    return p.parse_args()


async def _xg(league, seasons):
    m = {}
    for s in seasons:
        m.update(await get_xg_map(league, s))
    return m


def main():
    args = parse_args()
    seasons = [int(s) for s in args.seasons.split(",")]
    train_seasons = [s for s in seasons if s != args.test_season]

    print(f"🧱 Costruisco le feature (5 leghe, stagioni {seasons})...")
    frames = []
    for lid, name in LEAGUES:
        try:
            fx = load_seasons(lid, seasons)
            xg = asyncio.run(_xg(lid, seasons))
        except FileNotFoundError:
            print(f"   ⚠️ dati mancanti per {name}, salto")
            continue
        df = build_feature_frame(fx, xg, xi=args.xi, k=args.k)
        df["league"] = name
        frames.append(df)
        print(f"   {name}: {len(df)} righe")

    if not frames:
        print("❌ Nessun dato.")
        sys.exit(1)

    df = pd.concat(frames, ignore_index=True)
    cmp = train_and_evaluate(df, train_seasons, args.test_season)

    console = Console()
    console.print()
    console.rule(f"[bold]GBM vs PARAMETRICO — train {train_seasons} · test {args.test_season} "
                 f"(top-5 pooled)[/bold]")
    console.print(f"Righe train: [bold]{cmp.n_train}[/bold] · test: [bold]{cmp.n_test}[/bold]\n")

    table = Table(title="Chi predice meglio? (verde = vince)", header_style="bold cyan")
    table.add_column("Mercato")
    table.add_column("Metrica", justify="center")
    table.add_column("Parametrico", justify="right")
    table.add_column("GBM", justify="right")

    for market, res in cmp.binary.items():
        p, g = res["Parametrico"], res["GBM"]
        gwin = g.brier < p.brier
        table.add_row(
            market, "Brier ↓ / Skill",
            f"{p.brier:.4f} / {p.brier_skill:+.3f}",
            f"[{'green' if gwin else 'red'}]{g.brier:.4f}[/] / {g.brier_skill:+.3f}",
        )
    p1, g1 = cmp.result_1x2["Parametrico"], cmp.result_1x2["GBM"]
    gwin = g1.rps < p1.rps
    table.add_row(
        "1X2", "RPS ↓ / Brier",
        f"{p1.rps:.4f} / {p1.brier:.3f}",
        f"[{'green' if gwin else 'red'}]{g1.rps:.4f}[/] / {g1.brier:.3f}",
    )
    console.print(table)
    console.print("\n[dim]Time-split out-of-sample: allena sul passato, testa sul 2025 mai visto. "
                  "Se il GBM non batte il parametrico, il modello semplice basta.[/dim]\n")


if __name__ == "__main__":
    main()
