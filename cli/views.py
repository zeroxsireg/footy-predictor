"""Rich rendering of the lean pipeline (pure presentation, defensive against None)."""

from typing import Any, Dict, Iterable, List, Optional

from rich import box
from rich.console import Console
from rich.table import Table

ND = "n/d"
MANUAL_ODDS_NOTE = "quota non disponibile via API: inseriscila a mano da Bet365"
MIN_BETS_NOTE = "campione insufficiente ({n} bet): non concludere nulla"


def g(obj: Any, key: str, default: Any = None) -> Any:
    """Read a field from a dict or an object; None-safe."""
    if obj is None:
        return default
    value = obj.get(key, default) if isinstance(obj, dict) else getattr(obj, key, default)
    return default if value is None else value


def trunc(text: Optional[str], width: int = 18) -> str:
    """Truncate with an ellipsis (80-column terminals)."""
    text = text or ND
    return text if len(text) <= width else text[: width - 1] + "…"


def pct(p: Optional[float]) -> str:
    return f"{p * 100:.0f}" if isinstance(p, (int, float)) else ND


def odd(x: Optional[float]) -> str:
    return f"{x:.2f}" if isinstance(x, (int, float)) and x > 0 else ND


def money(x: Optional[float]) -> str:
    return f"{x:.2f} €" if isinstance(x, (int, float)) else ND


def signed_pct(x: Optional[float], digits: int = 1) -> str:
    """Fraction -> '+3.2%' colored green (edge/profit) or red (risk)."""
    if not isinstance(x, (int, float)):
        return ND
    color = "green" if x > 0 else "red" if x < 0 else "yellow"
    return f"[{color}]{x * 100:+.{digits}f}%[/{color}]"


def triple(probs: Optional[Dict[str, float]], keys: Iterable[str], fmt=pct) -> str:
    if not probs:
        return ND
    return "/".join(fmt(probs.get(k)) for k in keys)


def render_matches(console: Console, rows: List[Dict[str, Any]]) -> None:
    """One row per fixture: model vs market fair (Shin) probabilities and quotes."""
    table = Table(title="PARTITE: modello vs mercato (%, quote Bet365)", box=box.SIMPLE_HEAD,
                  title_style="bold cyan", pad_edge=False)
    for col in ("Partita", "Mod 1/X/2", "Fair 1/X/2", "Quote 1/X/2", "O2.5 m/f @q"):
        table.add_column(col, no_wrap=True, overflow="ellipsis")
    for r in rows:
        fx = r["fixture"]
        p = r.get("probs")
        model = {"1": g(p, "p1", None), "X": g(p, "px", None), "2": g(p, "p2", None)} if p else None
        f12, q12 = r.get("fair_1x2"), r.get("odds_1x2")
        fou, qou = r.get("fair_ou"), r.get("odds_ou")
        over_m = g(p, "p_over_2_5", None) if p else None
        ou = f"{pct(over_m)}/{pct((fou or {}).get('over'))} @{odd((qou or {}).get('over'))}"
        table.add_row(trunc(f"{fx.home}-{fx.away}", 20), triple(model, "1X2"),
                      triple(f12, "1X2"), triple(q12, "1X2", odd), ou)
    console.print(table)


def render_picks(console: Console, strategy: str, bankroll: Any, picks: List[Any],
                 names: Dict[int, str], day: str = "", placed: int = 0) -> None:
    head = f"[bold cyan]{strategy}[/bold cyan] {day}  cassa {money(bankroll)}"
    if placed:
        head += f"  ({placed} già piazzate)"
    if not picks:
        console.print(f"{head}: nessuna nuova singola")
        return
    table = Table(title=head, box=box.SIMPLE_HEAD, pad_edge=False, title_justify="left")
    for col in ("Partita", "Gioca", "Quota", "Book", "EV", "Stake"):
        table.add_column(col, no_wrap=True, overflow="ellipsis")
    for c in picks:
        table.add_row(trunc(names.get(c.fixture_id, str(c.fixture_id)), 20), f"{c.market} {c.selection}",
                      odd(c.odds), trunc(c.bookmaker, 10), signed_pct(c.ev), money(c.stake_amount))
    console.print(table)


def render_players(console: Console, fixture: Any, cands: List[Any], per_team: int = 5) -> None:
    """Booking candidates per team; never quotes/EV (not available via API)."""
    console.print(f"[bold cyan]AMMONITI {trunc(fixture.home, 16)} - {trunc(fixture.away, 16)}[/bold cyan]")
    if not cands:
        console.print("  [yellow]nessun candidato disponibile (rose/formazioni mancanti)[/yellow]")
        return
    teams: Dict[str, List[Any]] = {}
    for c in cands:
        teams.setdefault(c.team, []).append(c)
    for team, items in teams.items():
        table = Table(title=trunc(team, 24), box=box.SIMPLE_HEAD, pad_edge=False, title_justify="left")
        for col in ("Giocatore", "P amm.", "Gioca", "Nota"):
            table.add_column(col, no_wrap=True, overflow="ellipsis")
        for c in sorted(items, key=lambda x: x.p_booked, reverse=True)[:per_team]:
            table.add_row(trunc(c.name, 20), f"{c.p_booked * 100:.0f}%",
                          f"{c.start_prob * 100:.0f}%", trunc(c.note, 24))
        console.print(table)
    console.print(f"  [yellow]{MANUAL_ODDS_NOTE}[/yellow]")
