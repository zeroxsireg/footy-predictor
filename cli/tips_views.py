"""Rich rendering of the daily tips ("pronostici probabili"). Pure presentation, None-safe."""

from typing import Any, Dict, List, Optional

from rich import box
from rich.console import Console
from rich.table import Table

from cli.views import MANUAL_ODDS_NOTE, ND, g, odd, pct, trunc

PREFERRED_BOOK = "Bet365"
RELIABILITY_COLOR = {"alta": "green", "media": "yellow", "bassa": "red"}
MIN_ODDS_HELP = ("Quota minima = la quota sotto la quale NON conviene giocare il pronostico: "
                 "se Bet365 paga meno, il prezzo e' troppo basso rispetto alla probabilita' del modello.")
NO_GUARANTEE = ("La probabilita' NON e' una garanzia: un pronostico al 80% perde 1 volta su 5. "
                "Nessun consiglio d'investimento, solo stime statistiche.")
MULTIPLE_WARN = "la multipla moltiplica il margine del bookmaker: rende meno delle singole"


def score_summary(matrix: Optional[List[List[float]]]) -> str:
    """'1/X/2 nn/nn/nn  gol attesi h-a' from a joint score matrix (rows = home goals)."""
    try:
        p1 = px = p2 = xh = xa = 0.0
        for i, row in enumerate(matrix):
            for j, p in enumerate(row):
                p1, px, p2 = p1 + (p if i > j else 0), px + (p if i == j else 0), p2 + (p if i < j else 0)
                xh, xa = xh + i * p, xa + j * p
        return f"Modello 1/X/2 {pct(p1)}/{pct(px)}/{pct(p2)}  gol attesi {xh:.1f}-{xa:.1f}"
    except (TypeError, ValueError):
        return f"Modello 1/X/2 {ND}  gol attesi {ND}"


def quote_cell(quote: Any) -> str:
    """Real quote, with the bookmaker when it is not the preferred one; else the manual hint."""
    value = g(quote, "odds", None)
    if not isinstance(value, (int, float)) or value <= 0:
        return "[dim]da inserire a mano[/dim]"
    book = g(quote, "bookmaker", "")
    return odd(value) if not book or book == PREFERRED_BOOK else f"{odd(value)} ({trunc(book, 8)})"


def verdict_cell(conviene: Optional[bool]) -> str:
    if conviene is True:
        return "[bold green]SI'[/bold green]"
    if conviene is False:
        return "[bold red]NO[/bold red]"
    return "[yellow]?[/yellow]"


def reliability_cell(tip: Any) -> str:
    rel = g(tip, "reliability", ND)
    return f"[{RELIABILITY_COLOR.get(rel, 'white')}]{rel}[/{RELIABILITY_COLOR.get(rel, 'white')}]"


def render_day(console: Console, day: str, summaries: List[str], selected: List[Any],
               names: Dict[int, str], multiples: List[Any]) -> None:
    console.print(f"\n[bold cyan]== {day} ==[/bold cyan]")
    for line in summaries:
        console.print(f"[dim]{line}[/dim]")
    if not selected:
        console.print("[yellow]Nessun pronostico sopra la soglia di probabilita'.[/yellow]")
    else:
        table = Table(title="PRONOSTICI PROBABILI", box=box.SIMPLE_HEAD, pad_edge=False,
                      title_style="bold cyan", title_justify="left")
        for col, just in (("Partita", "left"), ("Pronostico", "left"), ("Prob.", "right"),
                          ("Equa", "right"), ("Min.", "right"), ("Bet365", "right"),
                          ("Conv.", "center"), ("Aff.", "left")):
            table.add_column(col, no_wrap=True, overflow="ellipsis", justify=just)
        for s in selected:
            tip = g(s, "tip")
            table.add_row(trunc(names.get(g(tip, "fixture_id", None), ND), 15),
                          trunc(g(tip, "label", ND), 17), f"{pct(g(tip, 'probability', None))}%",
                          odd(g(tip, "fair_odds", None)), odd(g(tip, "min_odds", None)),
                          quote_cell(g(s, "quote", None)), verdict_cell(g(s, "conviene", None)),
                          reliability_cell(tip))
        console.print(table)
    render_multiples(console, multiples, names)


def render_multiples(console: Console, multiples: List[Any], names: Dict[int, str]) -> None:
    if not multiples:
        return
    table = Table(title="MULTIPLE (2-3 selezioni, partite diverse)", box=box.SIMPLE_HEAD,
                  pad_edge=False, title_style="bold cyan", title_justify="left")
    for col, just in (("Selezioni", "left"), ("Prob.", "right"), ("Equa", "right"), ("Min.", "right")):
        table.add_column(col, no_wrap=False, justify=just)
    for m in multiples:
        legs = " + ".join(f"{trunc(names.get(g(t, 'fixture_id', None), ND), 10)} {g(t, 'label', ND)}"
                          for t in g(m, "legs", ()) or ())
        table.add_row(legs, f"{pct(g(m, 'probability', None))}%", odd(g(m, "fair_odds", None)),
                      odd(g(m, "min_odds", None)))
    console.print(table)
    console.print(f"[yellow]Attenzione: {MULTIPLE_WARN}.[/yellow]")


def render_footer(console: Console) -> None:
    console.print(f"\n[cyan]{MIN_ODDS_HELP}[/cyan]")
    console.print("Quota equa = 1 / probabilita'. Affidabilita' = abilita' del modello misurata "
                  "fuori campione su quel tipo di pronostico.")
    console.print(f"[yellow]{NO_GUARANTEE}[/yellow]")


def render_booked(console: Console, fixture: Any, cands: List[Any], per_team: int = 3) -> None:
    """Top booking candidates per team: probability only."""
    console.print(f"[bold cyan]AMMONITI {trunc(g(fixture, 'home', ND), 14)} - "
                  f"{trunc(g(fixture, 'away', ND), 14)}[/bold cyan]")
    if not cands:
        console.print("  [yellow]nessun candidato disponibile[/yellow]")
        return
    teams: Dict[str, List[Any]] = {}
    for c in cands:
        teams.setdefault(g(c, "team", ND), []).append(c)
    for team, items in teams.items():
        best = sorted(items, key=lambda x: g(x, "p_booked", 0.0), reverse=True)[:per_team]
        console.print(f"  {trunc(team, 16)}: " + ", ".join(
            f"{trunc(g(c, 'name', ND), 16)} {pct(g(c, 'p_booked', None))}%" for c in best))
