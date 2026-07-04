"""Human-readable rendering of a BacktestReport (Rich tables)."""

from rich.console import Console
from rich.table import Table

from backtest.runner import BacktestReport


def _brier_note(brier: float) -> str:
    if brier < 0.10:
        return "eccellente"
    if brier < 0.15:
        return "buono"
    if brier < 0.20:
        return "nella media"
    if brier < 0.25:
        return "debole"
    return "peggio del caso"


def print_report(report: BacktestReport, console: Console | None = None) -> None:
    console = console or Console()

    console.print()
    console.rule(
        f"[bold]BACKTEST — Lega {report.league_id} · Stagione {report.season}[/bold]"
    )
    console.print(
        f"Partite valutate: [bold]{report.total_matches_scored}[/bold]  "
        f"(escluse le prime {report.min_matches} giornate per squadra)\n"
    )

    # ── binary markets ────────────────────────────────────────────────────────
    table = Table(title="Mercati Sì/No", header_style="bold cyan")
    table.add_column("Mercato")
    table.add_column("N", justify="right")
    table.add_column("Brier", justify="right")
    table.add_column("Skill", justify="right")
    table.add_column("Azzeccate", justify="right")
    table.add_column("Prev. media", justify="right")
    table.add_column("Reale", justify="right")
    table.add_column("Giudizio")

    for r in report.binary:
        skill_style = "green" if r.brier_skill > 0 else "red"
        table.add_row(
            r.market,
            str(r.n),
            f"{r.brier:.3f}",
            f"[{skill_style}]{r.brier_skill:+.3f}[/{skill_style}]",
            f"{r.hit_rate:.1%}",
            f"{r.avg_prediction:.1%}",
            f"{r.base_rate:.1%}",
            _brier_note(r.brier),
        )
    console.print(table)

    # ── 1X2 ───────────────────────────────────────────────────────────────────
    m = report.result_1x2
    t2 = Table(title="Risultato 1X2", header_style="bold cyan")
    t2.add_column("N", justify="right")
    t2.add_column("Brier (multiclasse)", justify="right")
    t2.add_column("Azzeccate (argmax)", justify="right")
    t2.add_column("Base 1 / X / 2")
    base = m.per_class_base_rate
    t2.add_row(
        str(m.n),
        f"{m.brier:.3f}",
        f"{m.hit_rate:.1%}",
        f"{base['1']:.0%} / {base['X']:.0%} / {base['2']:.0%}",
    )
    console.print(t2)

    # ── calibration for the flagship market ───────────────────────────────────
    flagship = next((r for r in report.binary if r.market == "Over 2.5 Goals"), None)
    if flagship and flagship.calibration:
        console.print()
        ct = Table(
            title="Calibrazione — Over 2.5 (previsto vs reale per fascia)",
            header_style="bold magenta",
        )
        ct.add_column("Fascia probabilità")
        ct.add_column("Casi", justify="right")
        ct.add_column("Previsto medio", justify="right")
        ct.add_column("Reale", justify="right")
        ct.add_column("Scarto", justify="right")
        for label, count, avg_pred, actual in flagship.calibration:
            gap = actual - avg_pred
            gap_style = "green" if abs(gap) <= 0.05 else "yellow" if abs(gap) <= 0.10 else "red"
            ct.add_row(
                label, str(count), f"{avg_pred:.1%}", f"{actual:.1%}",
                f"[{gap_style}]{gap:+.1%}[/{gap_style}]",
            )
        console.print(ct)

    console.print(
        "\n[dim]Brier: 0=perfetto, 0.25=come lanciare una moneta. "
        "Skill>0 = meglio del prevedere sempre la media. "
        "Calibrazione buona = scarto vicino a 0.[/dim]\n"
    )
