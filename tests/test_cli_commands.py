"""CLI commands with fakes: no network, ledger on tmp_path (never data/footy_predictor.db)."""

import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from rich.console import Console

from cli import commands
from cli.deps import Deps
from cli.report_cmd import cmd_report
from core import devig, value_engine
from core.contracts import (MARKET_1X2, MARKET_OU25, STRATEGIES, FixtureRef, FixtureResult,
                            MatchProbs, PlayerCandidate, PriceQuote)
from core.ledger import Ledger

NOW = datetime.now(timezone.utc)


def fx(fid=1, home="Internazionale Milano Football Club", away="Juve", kick=None):
    return FixtureRef(fid, kick or NOW + timedelta(hours=5), home, away, 10, 20, 135, 2026)


def quote(fid, market, odds, book="Bet365"):
    return PriceQuote(fid, market, book, 8, odds, NOW)


PRICES = {MARKET_1X2: quote(1, MARKET_1X2, {"1": 3.0, "X": 3.4, "2": 2.4}),
          MARKET_OU25: quote(1, MARKET_OU25, {"over": 1.9, "under": 1.95})}
BENCH = {MARKET_1X2: quote(1, MARKET_1X2, {"1": 3.0, "X": 3.4, "2": 2.4}, "Pinnacle")}


def make_deps(tmp_path, fixtures=None, prices=None, result=None, probs=None, players=None):
    console = Console(width=80, force_terminal=False)
    return Deps(
        ledger=Ledger(str(tmp_path / "l.db")), console=console, strategies=STRATEGIES,
        refresh=lambda *a: {}, upcoming=_async(fixtures if fixtures is not None else [fx()]),
        prices=_async(PRICES if prices is None else prices), benchmark=_async(BENCH),
        result=_async(result),
        predict=lambda f: probs or MatchProbs(f.fixture_id, 0.55, 0.25, 0.20, 0.6, "fake"),
        build_candidates=value_engine.build_candidates, select_daily=value_engine.select_daily,
        fair_probs=devig.shin,
        players=_async(players if players is not None else [
            PlayerCandidate(1, 100 + i, f"Giocatore{i}", "Internazionale", "D", 0.3, 0.9,
                            0.27 - i * 0.01, "nota") for i in range(7)]))


def _async(value):
    async def fn(*a):
        return value
    return fn


def run(coro):
    return asyncio.run(coro)


def test_today_report_and_ledger(tmp_path, capsys):
    deps = make_deps(tmp_path)
    out = run(commands.cmd_today(deps))
    text = capsys.readouterr().out
    assert out["fixtures"] == 1
    assert "Internazionale Mila…" in text and "Football Club" not in text  # 80 cols
    assert "55/25/20" in text                                   # model probs
    assert "3.00/3.40/2.40" in text                             # quotes
    assert "quota non disponibile via API" in text
    assert "Giocatore4" in text and "Giocatore5" not in text    # top 5 per team
    assert "EV" in text and "+" in text
    # picks persisted with the real bookmaker, predictions of all fixtures too
    rows = deps.ledger.conn.execute("SELECT bookmaker, stake_amount FROM ledger_bets").fetchall()
    assert rows and all(r["bookmaker"] == "Bet365" and r["stake_amount"] > 0 for r in rows)
    assert deps.ledger.conn.execute("SELECT COUNT(*) FROM ledger_predictions").fetchone()[0] == 1
    assert deps.ledger.conn.execute("SELECT COUNT(*) FROM ledger_player_predictions").fetchone()[0] == 7
    assert deps.ledger.conn.execute(
        "SELECT COUNT(*) FROM ledger_snapshots WHERE kind='benchmark_pick'").fetchone()[0] == 1


def test_today_dry_run_saves_nothing(tmp_path, capsys):
    deps = make_deps(tmp_path)
    run(commands.cmd_today(deps, dry_run=True))
    assert "--dry-run" in capsys.readouterr().out
    assert deps.ledger.conn.execute("SELECT COUNT(*) FROM ledger_predictions").fetchone()[0] == 0
    assert deps.ledger.conn.execute("SELECT COUNT(*) FROM ledger_bets").fetchone()[0] == 0


def test_today_missing_markets_and_model_do_not_crash(tmp_path, capsys):
    deps = make_deps(tmp_path, prices={})
    deps.predict = lambda f: (_ for _ in ()).throw(RuntimeError("boom"))
    run(commands.cmd_today(deps))
    text = capsys.readouterr().out
    assert "n/d" in text and "nessuna nuova singola" in text


def test_today_no_fixtures(tmp_path, capsys):
    run(commands.cmd_today(make_deps(tmp_path, fixtures=[])))
    assert "Nessuna partita" in capsys.readouterr().out


def test_close_only_imminent_open_fixtures_without_closing(tmp_path, capsys):
    deps = make_deps(tmp_path, fixtures=[fx(1, kick=NOW + timedelta(minutes=10)),
                                         fx(2, kick=NOW + timedelta(hours=3))])
    run(commands.cmd_today(deps))
    capsys.readouterr()
    deps.upcoming = _async([fx(1, kick=NOW + timedelta(minutes=10)),
                            fx(2, kick=NOW + timedelta(hours=3))])
    assert run(commands.cmd_close(deps, 15)) == 1
    n = deps.ledger.conn.execute("SELECT COUNT(*) FROM ledger_snapshots WHERE kind='close'").fetchone()[0]
    assert n == 2
    assert run(commands.cmd_close(deps, 15)) == 0       # already has closing
    assert "Nessuna partita da chiudere" in capsys.readouterr().out


def test_settle_prints_outcome_profit_clv_and_updates_players(tmp_path, capsys):
    deps = make_deps(tmp_path)
    run(commands.cmd_today(deps))
    deps.ledger.record_closing(1, PRICES, BENCH)
    capsys.readouterr()
    deps.result = _async(FixtureResult(1, "NS", None, None))
    assert run(commands.cmd_settle(deps)) == 0          # not finished: untouched
    assert deps.ledger.conn.execute("SELECT COUNT(*) FROM ledger_results").fetchone()[0] == 0
    deps.result = _async(FixtureResult(1, "FT", 2, 0, booked_player_ids=[100]))
    assert run(commands.cmd_settle(deps)) == 1
    text = capsys.readouterr().out
    assert "2-0" in text and "won" in text and "CLV" in text
    assert deps.ledger.conn.execute(
        "SELECT booked FROM ledger_player_predictions WHERE player_id=100").fetchone()[0] == 1


def test_signed_pct_colors_and_none():
    from cli.views import signed_pct
    assert signed_pct(0.05).startswith("[green]") and signed_pct(-0.05).startswith("[red]")
    assert signed_pct(0.0).startswith("[yellow]") and signed_pct(None) == "n/d"


def test_report_honesty_and_table(tmp_path, capsys):
    deps = make_deps(tmp_path)
    cmd_report(deps)
    text = capsys.readouterr().out
    for s in STRATEGIES:
        assert s in text
    assert "raw: campione insufficiente (0 bet): non concludere nulla" in text
    assert "CALIBRAZIONE" in text
    cmd_report(deps, "raw")
    assert "sharp_gap" not in capsys.readouterr().out


def test_players_command(tmp_path, capsys):
    deps = make_deps(tmp_path)
    run(commands.cmd_players(deps, 1))
    assert "Giocatore0" in capsys.readouterr().out
    run(commands.cmd_players(deps, 999))
    assert "non trovata" in capsys.readouterr().out


def test_router_help_and_unknown(capsys):
    from cli.simple_main import main
    main(["--help"])
    text = capsys.readouterr().out
    for cmd in ("today", "close", "settle", "report", "players", "--dry-run"):
        assert cmd in text
    main(["boh"])
    assert "sconosciuto" in capsys.readouterr().out


def test_router_runs_with_injected_deps(tmp_path, capsys):
    from cli.simple_main import _run_lean
    _run_lean("today", ["--dry-run", "--days", "1"], deps=make_deps(tmp_path))
    assert "55/25/20" in capsys.readouterr().out


def _three_days():
    base = (NOW + timedelta(days=1)).replace(hour=14, minute=0)
    return [fx(i, kick=base + timedelta(days=(i - 1) // 4)) for i in range(1, 13)]


def test_max_three_per_day_and_rerun_respects_placed(tmp_path, capsys):
    deps = make_deps(tmp_path, fixtures=_three_days(), prices={
        m: quote(1, m, q.odds) for m, q in PRICES.items()})
    out = run(commands.cmd_today(deps, dry_run=True))
    for strategy in ("raw", "blend50"):
        days = {}
        for b in out["picks"][strategy]:
            k = next(f.kickoff.astimezone(commands.MARKET_TZ).date() for f in _three_days()
                     if f.fixture_id == b.fixture_id)
            days[k] = days.get(k, 0) + 1
        assert len(days) == 3 and all(n == 3 for n in days.values())
    capsys.readouterr()
    run(commands.cmd_today(deps))                       # first real run persists
    n1 = deps.ledger.conn.execute("SELECT COUNT(*) FROM ledger_bets WHERE strategy='raw'").fetchone()[0]
    run(commands.cmd_today(deps))                       # rerun: nothing more above cap
    n2 = deps.ledger.conn.execute("SELECT COUNT(*) FROM ledger_bets WHERE strategy='raw'").fetchone()[0]
    assert n1 == n2 == 9
    deps.ledger.conn.execute("DELETE FROM ledger_bets WHERE id IN (SELECT id FROM ledger_bets "
                             "WHERE strategy='raw' ORDER BY id LIMIT 1)")
    run(commands.cmd_today(deps))                       # 2 placed on that day -> adds at most 1
    n3 = deps.ledger.conn.execute("SELECT COUNT(*) FROM ledger_bets WHERE strategy='raw'").fetchone()[0]
    assert n3 == 9


def test_dry_run_skips_refresh_and_started_not_playable(tmp_path, capsys):
    calls = []
    deps = make_deps(tmp_path, fixtures=[fx(1, kick=NOW - timedelta(hours=1)), fx(2)])
    deps.refresh = lambda *a: calls.append(a)
    out = run(commands.cmd_today(deps, dry_run=True))
    text = capsys.readouterr().out
    assert calls == [] and "nessun refresh" in text
    assert "non giocabili" in text
    assert {b.fixture_id for bs in out["picks"].values() for b in bs} == {2}
    run(commands.cmd_today(deps))
    assert len(calls) == 1


def test_rerun_passes_placed_and_adds_nothing(tmp_path):
    seen = []

    def spy(cands, state, max_picks=3, already_placed=()):
        seen.append(len(already_placed))
        return value_engine.select_daily(cands, state, max_picks, already_placed)

    deps = make_deps(tmp_path, fixtures=_three_days())
    deps.select_daily = spy
    run(commands.cmd_today(deps))
    assert set(seen) == {0}
    seen.clear()
    out = run(commands.cmd_today(deps))
    assert seen.count(3) == 6                           # raw+blend50 x 3 days
    assert out["picks"]["raw"] == []                    # day already full: nothing new
