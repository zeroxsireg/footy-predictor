"""`report` command: per-strategy performance and calibration, with honesty thresholds."""

from typing import Optional

from rich import box
from rich.table import Table

from cli.deps import Deps
from cli.views import MIN_BETS_NOTE, ND, g, money, signed_pct

MIN_BETS_CLV = 100      # below this the CLV mean is noise
MIN_BETS_ROI = 30       # below this ROI/hit-rate are anecdotes


def _num(x, digits: int = 3) -> str:
    return f"{x:.{digits}f}" if isinstance(x, (int, float)) else ND


def _hit(x) -> str:
    return f"{x * 100:.0f}%" if isinstance(x, (int, float)) else ND


def cmd_report(deps: Deps, strategy: Optional[str] = None) -> None:
    c = deps.console
    strategies = [strategy] if strategy else list(deps.strategies)
    table = Table(title="PAPER TRADING per strategia", box=box.SIMPLE_HEAD, pad_edge=False,
                  title_style="bold cyan")
    for col in ("Strategia", "Cassa", "Bet", "ROI", "Hit", "DD max", "CLV"):
        table.add_column(col, no_wrap=True)
    notes = []
    for s in strategies:
        try:
            st = deps.ledger.stats(s) or {}
        except Exception as exc:
            c.print(f"[yellow]stats {s} non disponibili ({exc})[/yellow]")
            st = {}
        n = int(g(st, "n_bets", 0) or 0)
        cash = g(deps.ledger.bankroll_state(s), "bankroll", None)
        roi = signed_pct(g(st, "roi", None)) if n >= MIN_BETS_ROI else ND
        clv = signed_pct(g(st, "avg_clv", None), 2) if n >= MIN_BETS_CLV else ND
        table.add_row(s, money(cash), str(n), roi,
                      _hit(g(st, "hit_rate", None)) if n >= MIN_BETS_ROI else ND,
                      signed_pct(g(st, "max_drawdown", None)), clv)
        if n < MIN_BETS_CLV:
            notes.append(f"{s}: {MIN_BETS_NOTE.format(n=n)} (CLV richiede {MIN_BETS_CLV} bet)")
    c.print(table)
    for note in notes:
        c.print(f"[yellow]{note}[/yellow]")
    _calibration(deps)


def _calibration(deps: Deps) -> None:
    c = deps.console
    try:
        cal = deps.ledger.calibration() or {}
    except Exception as exc:
        c.print(f"[yellow]calibrazione non disponibile ({exc})[/yellow]")
        return
    n = int(g(cal, "n_1x2", 0) or 0)
    t = Table(title=f"CALIBRAZIONE vs chiusura ({n} partite 1X2, {g(cal, 'n_ou25', 0)} O/U 2.5)",
              box=box.SIMPLE_HEAD, pad_edge=False)
    for col in ("", "Brier 1X2", "RPS 1X2", "Brier Over"):
        t.add_column(col)
    t.add_row("modello", _num(g(cal, "brier_1x2_model")), _num(g(cal, "rps_model")),
              _num(g(cal, "brier_over_model")))
    t.add_row("mercato", _num(g(cal, "brier_1x2_market")), _num(g(cal, "rps_market")),
              _num(g(cal, "brier_over_market")))
    c.print(t)
    if n < MIN_BETS_CLV:
        c.print(f"[yellow]{MIN_BETS_NOTE.format(n=n)}[/yellow]")
    p = g(cal, "players", {}) or {}
    pn = int(g(p, "n", 0) or 0)
    c.print(f"Ammoniti: Brier {_num(g(p, 'brier'))}  precision@{g(p, 'k', 3)} "
            f"{_num(g(p, 'precision_at_k'))}  ({pn} candidati)")
    if pn < MIN_BETS_CLV:
        c.print(f"[yellow]{MIN_BETS_NOTE.format(n=pn)}[/yellow]")
