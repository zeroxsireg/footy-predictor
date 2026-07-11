"""Shared Rich renderer for a prediction card."""

from typing import Dict, Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table


def _pct(x: float) -> str:
    return f"{x * 100:.0f}%"


def render_card(console: Console, card: Dict, actual: Optional[Dict] = None) -> None:
    g = card.get("goals")
    if not g:
        console.print("[red]Pronostico non disponibile (dati insufficienti).[/red]")
        return

    title = "🔮 PRONOSTICO (partita futura)" if card.get("upcoming") else "⚽ SCHEDA PRONOSTICO"
    console.print()
    console.print(Panel.fit(
        f"[bold]{card['home']}  vs  {card['away']}[/bold]\n"
        f"{card['date'][:10]}  ·  Arbitro: {card.get('referee') or 'n/d'}",
        title=title, border_style="cyan",
    ))

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
    console.print(t)

    if card.get("cards"):
        cc = card["cards"]; over = cc["over"]
        console.print(Panel.fit(
            f"Attesi: [bold]{cc['expected']:.1f}[/bold] cartellini   ·   "
            f"Over 3.5 {_pct(over[3.5])}  ·  Over 4.5 {_pct(over[4.5])}  ·  Over 5.5 {_pct(over[5.5])}",
            title="🟨 Cartellini squadra", border_style="yellow",
        ))

    if card.get("players"):
        booked = set((actual or {}).get("booked") or [])
        pt = Table(title="🎯 Giocatori a rischio ammonizione (top 6)", header_style="bold magenta")
        pt.add_column("Giocatore"); pt.add_column("Ruolo", justify="center")
        pt.add_column("Prob.", justify="right"); pt.add_column("Esito", justify="center")
        for p in card["players"]:
            hit = "🟨" if p["name"] in booked else ""
            pt.add_row(p["name"], p["position"], _pct(p["prob"]), hit)
        console.print(pt)

    if actual:
        real = f"Risultato reale: [bold]{actual['home_goals']}-{actual['away_goals']}[/bold]"
        if actual.get("total_cards") is not None:
            real += f"   ·   cartellini: {actual['total_cards']}"
        if actual.get("booked"):
            real += f"   ·   ammoniti: {', '.join(actual['booked'][:8])}"
        console.print(Panel.fit(real, border_style="green"))
    console.print()
