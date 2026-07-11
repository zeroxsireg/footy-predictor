#!/usr/bin/env python3
"""
Prediction card demo.

Generates the full prediction card for a single match — 1X2, Over/Under, BTTS,
multigol, team cards and at-risk players — using only data available before the
match, and shows the ACTUAL result alongside so you can judge it.

Off-season demo: runs on a real, already-played match.

Usage:
    python predict_match.py                              # Serie A: Inter vs Milan 2024/25
    python predict_match.py --home Roma --away Lazio
    python predict_match.py --league 140 --home Barcelona --away Real Madrid
"""

import argparse
import sys

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from backtest.card import build_prediction_card, find_fixture_id


def parse_args():
    p = argparse.ArgumentParser(description="Prediction card")
    p.add_argument("--league", type=int, default=135)
    p.add_argument("--season", type=int, default=2024)
    p.add_argument("--history", type=str, default="2023")
    p.add_argument("--home", type=str, default="Inter")
    p.add_argument("--away", type=str, default="AC Milan")
    p.add_argument("--fixture-id", type=int, default=None)
    return p.parse_args()


def _pct(x):
    return f"{x*100:.0f}%"


def main():
    args = parse_args()
    history = [int(s) for s in args.history.split(",") if s.strip()]

    fid = args.fixture_id or find_fixture_id(args.league, args.season, args.home, args.away)
    if fid is None:
        print(f"❌ Partita non trovata: {args.home} vs {args.away} (lega {args.league}, {args.season})")
        sys.exit(1)

    card = build_prediction_card(args.league, fid, season=args.season, history_seasons=history)
    if not card or not card["goals"]:
        print("❌ Impossibile generare il pronostico (dati insufficienti per questa partita).")
        sys.exit(1)

    c = Console()
    g = card["goals"]
    c.print()
    c.print(Panel.fit(
        f"[bold]{card['home']}  vs  {card['away']}[/bold]\n"
        f"{card['date'][:10]}  ·  Arbitro: {card['referee'] or 'n/d'}",
        title="⚽ SCHEDA PRONOSTICO", border_style="cyan",
    ))

    # ── esiti principali ──
    t = Table(show_header=False, box=None, padding=(0, 2))
    t.add_column(); t.add_column()
    t.add_row("[bold]1X2[/bold]",
              f"1 {_pct(g['result_1'])}   ·   X {_pct(g['result_X'])}   ·   2 {_pct(g['result_2'])}")
    t.add_row("[bold]Gol[/bold]",
              f"Over 1.5 {_pct(g['over_1_5'])}  ·  Over 2.5 {_pct(g['over_2_5'])}  ·  "
              f"Over 3.5 {_pct(g['over_3_5'])}  ·  BTTS {_pct(g['btts_yes'])}")
    t.add_row("[bold]Multigol[/bold]",
              f"1-2 {_pct(g['mg_total_1_2'])}  ·  2-3 {_pct(g['mg_total_2_3'])}  ·  "
              f"1-3 {_pct(g['mg_total_1_3'])}  ·  2-4 {_pct(g['mg_total_2_4'])}")
    t.add_row("[bold]MG Casa/Tras.[/bold]",
              f"Casa 1-3 {_pct(g['mg_home_1_3'])}  ·  Trasferta 1-3 {_pct(g['mg_away_1_3'])}")
    c.print(t)

    # ── cartellini ──
    if card["cards"]:
        cc = card["cards"]
        over = cc["over"]
        c.print(Panel.fit(
            f"Attesi: [bold]{cc['expected']:.1f}[/bold] cartellini   ·   "
            f"Over 3.5 {_pct(over[3.5])}  ·  Over 4.5 {_pct(over[4.5])}  ·  Over 5.5 {_pct(over[5.5])}",
            title="🟨 Cartellini squadra", border_style="yellow",
        ))

    # ── giocatori a rischio ──
    if card["players"]:
        booked_set = set(card["actual"].get("booked") or [])
        pt = Table(title="🎯 Giocatori a rischio ammonizione (top 6)", header_style="bold magenta")
        pt.add_column("Giocatore"); pt.add_column("Ruolo", justify="center")
        pt.add_column("Prob.", justify="right"); pt.add_column("Esito", justify="center")
        for p in card["players"]:
            hit = "🟨" if p["name"] in booked_set else ""
            pt.add_row(p["name"], p["position"], _pct(p["prob"]), hit)
        c.print(pt)

    # ── risultato reale (demo) ──
    a = card["actual"]
    real = f"Risultato reale: [bold]{a['home_goals']}-{a['away_goals']}[/bold]"
    if a.get("total_cards") is not None:
        real += f"   ·   cartellini: {a['total_cards']}"
    if a.get("booked"):
        real += f"   ·   ammoniti: {', '.join(a['booked'][:8])}"
    c.print(Panel.fit(real, border_style="green"))
    c.print("[dim]Pronostico generato con i soli dati precedenti alla partita "
            "(nessun leakage). 🟨 = giocatore effettivamente ammonito.[/dim]\n")


if __name__ == "__main__":
    main()
