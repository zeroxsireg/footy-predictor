#!/usr/bin/env python3
"""
Batch prediction for a whole matchday — a compact "coupon" view.

Off-season demo: predicts every match of a historical round from prior data.

Usage:
    python predict_round.py                      # Serie A 2024, round 20
    python predict_round.py --league 140 --round 30
"""

import argparse
import sys

from rich.console import Console
from rich.table import Table

from backtest.card import predict_round


def parse_args():
    p = argparse.ArgumentParser(description="Matchday prediction")
    p.add_argument("--league", type=int, default=135)
    p.add_argument("--season", type=int, default=2024)
    p.add_argument("--history", type=str, default="2023")
    p.add_argument("--round", type=int, default=20)
    return p.parse_args()


def _pct(x):
    return f"{x*100:.0f}%"


def main():
    args = parse_args()
    history = [int(s) for s in args.history.split(",") if s.strip()]
    round_name = f"Regular Season - {args.round}"

    cards = predict_round(args.league, season=args.season,
                          history_seasons=history, round_name=round_name)
    if not cards:
        print(f"❌ Nessuna partita per '{round_name}' (lega {args.league}, {args.season}).")
        sys.exit(1)

    c = Console()
    table = Table(title=f"📋 PRONOSTICI GIORNATA {args.round} — Lega {args.league} · {args.season}",
                  header_style="bold cyan")
    table.add_column("Partita")
    table.add_column("Segno", justify="center")
    table.add_column("O/U 2.5", justify="center")
    table.add_column("BTTS", justify="center")
    table.add_column("MG 1-3", justify="center")
    table.add_column("Cartellini", justify="center")
    table.add_column("Top ammonito", justify="left")

    for card in cards:
        g = card["goals"]
        sign = max([("1", g["result_1"]), ("X", g["result_X"]), ("2", g["result_2"])],
                   key=lambda x: x[1])
        cards_txt = f"{card['cards']['expected']:.1f}" if card.get("cards") else "—"
        top_player = card["players"][0]["name"] if card.get("players") else "—"
        table.add_row(
            f"{card['home']} - {card['away']}",
            f"{sign[0]} ({_pct(sign[1])})",
            f"O {_pct(g['over_2_5'])}",
            _pct(g["btts_yes"]),
            _pct(g["mg_total_1_3"]),
            cards_txt,
            top_player,
        )
    c.print()
    c.print(table)
    c.print("\n[dim]Ogni pronostico usa i soli dati precedenti alla partita. "
            "Segno = esito 1X2 più probabile.[/dim]\n")


if __name__ == "__main__":
    main()
