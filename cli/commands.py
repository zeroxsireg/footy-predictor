"""Command orchestration: today / close / settle / players (thin, dependency-injected)."""

import asyncio
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from typing import Any, Dict, List, Optional

from core.contracts import MARKET_1X2, MARKET_OU25
from cli.deps import Deps, maybe_await
from cli.ledger_view import fixture_bets, has_closing
from cli.views import (ND, g, money, odd, render_matches, render_picks, render_players,
                       signed_pct)

MAX_PICKS = 3
MARKET_TZ = ZoneInfo("Europe/Rome")
DEFAULT_BANKROLL = 50.0


def _odds(quotes: Optional[Dict[str, Any]], market: str) -> Optional[Dict[str, float]]:
    return g((quotes or {}).get(market), "odds", None)


async def _safe(deps: Deps, fn, *args, default=None, label: str = ""):
    """Call an injected callable; a failure or missing callable degrades to `default`."""
    if fn is None:
        return default
    try:
        return await maybe_await(fn(*args))
    except Exception as exc:  # rule CLI n.2: never crash on a missing market/module
        deps.console.print(f"[yellow]attenzione: {label or 'chiamata'} non riuscita ({exc})[/yellow]")
        return default


SELECTIONS = {MARKET_1X2: ("1", "X", "2"), MARKET_OU25: ("over", "under")}


async def _fair(deps: Deps, odds: Optional[Dict[str, float]], market: str):
    """Shin fair probabilities as {selection: p}; None when odds are missing/incomplete."""
    sels = SELECTIONS[market]
    if not odds or any(s not in odds for s in sels):
        return None
    fair = await _safe(deps, deps.fair_probs, [odds[s] for s in sels], label="probabilità fair")
    return dict(zip(sels, fair)) if fair else None


async def cmd_today(deps: Deps, days: int = 3, dry_run: bool = False,
                    bankroll: float = DEFAULT_BANKROLL) -> Dict[str, Any]:
    c = deps.console
    if dry_run:
        c.print("[yellow]--dry-run: nessun refresh dei file e nessuna scrittura[/yellow]")
    else:
        with c.status("Aggiorno i dati della stagione..."):
            await _safe(deps, deps.refresh, deps.league_id, deps.season, label="refresh dati")
    with c.status("Cerco le partite in arrivo..."):
        fixtures = await _safe(deps, deps.upcoming, deps.league_id, deps.season, days,
                               default=[], label="partite in arrivo")
    if not fixtures:
        c.print("[yellow]Nessuna partita in arrivo.[/yellow]")
        return {"fixtures": 0, "picks": {}}

    data: Dict[int, Dict[str, Any]] = {}
    with c.status("Modello e quote (Bet365 + Pinnacle)..."):
        for fx in fixtures:
            probs = await _safe(deps, deps.predict, fx, label=f"modello {fx.fixture_id}")
            quotes = await _safe(deps, deps.prices, fx.fixture_id, default={}, label="quote")
            bench = await _safe(deps, deps.benchmark, fx.fixture_id, default={}, label="benchmark")
            data[fx.fixture_id] = {"fixture": fx, "probs": probs, "quotes": quotes or {},
                                   "bench": bench or {}}

    rows = []
    for d in data.values():
        o12, oou = _odds(d["quotes"], MARKET_1X2), _odds(d["quotes"], MARKET_OU25)
        rows.append({**d, "odds_1x2": o12, "odds_ou": oou,
                     "fair_1x2": await _fair(deps, _odds(d["bench"], MARKET_1X2) or o12, MARKET_1X2),
                     "fair_ou": await _fair(deps, _odds(d["bench"], MARKET_OU25) or oou, MARKET_OU25)})
    render_matches(c, rows)

    names = {fid: f"{d['fixture'].home}-{d['fixture'].away}" for fid, d in data.items()}
    now = datetime.now(timezone.utc)
    started = [d["fixture"] for d in data.values() if d["fixture"].kickoff <= now]
    if started:
        c.print("[yellow]In corso/finite, non giocabili: "
                + ", ".join(f"{f.home}-{f.away}" for f in started) + "[/yellow]")
    by_day: Dict[Any, List[int]] = {}
    for d in sorted(data.values(), key=lambda d: d["fixture"].kickoff):
        if d["fixture"].kickoff > now:
            day = d["fixture"].kickoff.astimezone(MARKET_TZ).date()
            by_day.setdefault(day, []).append(d["fixture"].fixture_id)
    picks: Dict[str, List[Any]] = {}
    for strategy in deps.strategies:
        state = await _safe(deps, deps.ledger.bankroll_state, strategy, label="cassa")
        cash = g(state, "bankroll", bankroll if state is None else None)
        picks[strategy] = []
        for day, fids in by_day.items():
            cands: List[Any] = []
            for fid in fids:
                d = data[fid]
                if d["probs"] is None:
                    continue
                cands += await _safe(deps, deps.build_candidates, fid, d["probs"], d["quotes"],
                                     d["bench"], strategy, default=[],
                                     label=f"candidati {strategy}") or []
            placed = await _safe(deps, deps.ledger.bets_for_fixtures, strategy, fids, default=[],
                                 label="singole già piazzate") or []
            chosen = await _safe(deps, deps.select_daily, cands, state, MAX_PICKS, placed,
                                 default=[], label=f"selezione {strategy}") or []
            picks[strategy] += chosen
            render_picks(c, strategy, cash, chosen, names, day.strftime("%d/%m"), len(placed))

    all_players: List[Any] = []
    with c.status("Candidati ammoniti..."):
        for d in data.values():
            cands = await _safe(deps, deps.players, d["fixture"], default=[], label="ammoniti") or []
            all_players += cands
            render_players(c, d["fixture"], cands)
    if dry_run:
        c.print("[yellow]--dry-run: nulla salvato nel ledger[/yellow]")
    else:
        _save(deps, data, picks, all_players)
    return {"fixtures": len(fixtures), "picks": picks}


def _save(deps: Deps, data: Dict[int, Dict[str, Any]], picks: Dict[str, List[Any]],
          players: List[Any]) -> None:
    led = deps.ledger
    led.record_predictions([d["probs"] for d in data.values() if d["probs"] is not None])
    for d in data.values():
        for quote in d["quotes"].values():
            led.record_snapshot(quote, "pick")
        for quote in d["bench"].values():
            led.record_snapshot(quote, "benchmark_pick")
    bets = [b for chosen in picks.values() for b in chosen]
    inserted = led.record_bets(bets) if bets else 0
    if players:
        led.record_player_predictions(players)
    deps.console.print(f"Salvato nel ledger: {len(data)} partite, {inserted} nuove singole, "
                       f"{len(players)} candidati ammoniti.")


async def cmd_close(deps: Deps, minutes: int = 15) -> int:
    now = datetime.now(timezone.utc)
    limit = now + timedelta(minutes=minutes)
    open_ids = set(deps.ledger.open_fixtures() or [])
    fixtures = await _safe(deps, deps.upcoming, deps.league_id, deps.season, 2, default=[],
                           label="partite in arrivo") or []
    done = 0
    for fx in fixtures:
        if fx.fixture_id not in open_ids or has_closing(deps.ledger, fx.fixture_id):
            continue
        if not now <= fx.kickoff <= limit:
            continue
        with deps.console.status(f"Chiusura partita {fx.fixture_id}..."):
            quotes = await _safe(deps, deps.prices, fx.fixture_id, default={}, label="quote chiusura")
            bench = await _safe(deps, deps.benchmark, fx.fixture_id, default={}, label="benchmark")
        if quotes or bench:
            deps.ledger.record_closing(fx.fixture_id, quotes or {}, bench or {})
            done += 1
            deps.console.print(f"Chiusura salvata: {fx.home}-{fx.away}")
    if not done:
        deps.console.print(f"Nessuna partita da chiudere nei prossimi {minutes} minuti.")
    return done


async def cmd_settle(deps: Deps) -> int:
    settled = 0
    for fid in deps.ledger.unsettled_fixtures() or []:
        result = await _safe(deps, deps.result, fid, label=f"risultato {fid}")
        if result is None or not result.finished:
            continue
        deps.ledger.settle_fixture(result)
        deps.ledger.settle_players(fid, list(result.booked_player_ids))
        settled += 1
        deps.console.print(f"[bold cyan]Partita {fid}[/bold cyan] {result.home_goals}-{result.away_goals}")
        for b in fixture_bets(deps.ledger, fid):
            profit = g(b, "profit", None)
            color = "green" if isinstance(profit, (int, float)) and profit > 0 else "red"
            deps.console.print(
                f"  {b['strategy']} {b['market']} {b['selection']} @{odd(b['odds'])}: "
                f"{g(b, 'status', ND)} [{color}]{money(profit)}[/{color}]  "
                f"CLV {signed_pct(g(b, 'clv', None), 2)}")
    if not settled:
        deps.console.print("Nessuna partita finita da liquidare.")
    return settled


async def cmd_players(deps: Deps, fixture_id: int) -> None:
    with deps.console.status("Cerco la partita..."):
        fixtures = await _safe(deps, deps.upcoming, deps.league_id, deps.season, 7, default=[],
                               label="partite")
    fx = next((x for x in fixtures or [] if x.fixture_id == fixture_id), None)
    if fx is None:
        deps.console.print(f"[red]Partita {fixture_id} non trovata tra le prossime.[/red]")
        return
    with deps.console.status("Calcolo i candidati ammoniti..."):
        cands = await _safe(deps, deps.players, fx, default=[], label="ammoniti")
    render_players(deps.console, fx, cands or [])


def run(coro):
    """Sync entry for the router."""
    return asyncio.run(coro)
