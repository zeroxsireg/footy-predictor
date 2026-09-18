"""Dependency container of the lean CLI: every collaborator is an injectable callable.

Tests pass fakes; production wiring (`build_default_deps`) imports the real modules lazily,
so the CLI still starts (and reports a clear Italian error) if a module is missing.
"""

import importlib
import inspect
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from rich.console import Console

SERIE_A_KEY = "serie_a"


async def maybe_await(value: Any) -> Any:
    """Await `value` if it is awaitable (market_data is async, predictor is sync)."""
    if inspect.isawaitable(value):
        return await value
    return value


def serie_a_league_id() -> int:
    """Serie A league id from the SSOT (config/leagues.py)."""
    from config.leagues import get_league_manager
    return get_league_manager().get_league(SERIE_A_KEY).api_league_id


@dataclass
class Deps:
    """Callables + ledger used by the commands (missing pieces degrade to n/d)."""
    ledger: Any
    console: Console = field(default_factory=Console)
    league_id: int = 135
    season: Optional[int] = None
    refresh: Optional[Callable] = None            # (league_id, season) -> dict
    upcoming: Optional[Callable] = None           # (league_id, season, days) -> [FixtureRef]
    prices: Optional[Callable] = None             # (fixture_id) -> {market: PriceQuote}
    benchmark: Optional[Callable] = None          # (fixture_id) -> {market: PriceQuote}
    result: Optional[Callable] = None             # (fixture_id) -> FixtureResult | None
    predict: Optional[Callable] = None            # (fixture) -> MatchProbs
    build_candidates: Optional[Callable] = None   # (fixture_id, probs, quotes, benchmark, strategy)
    select_daily: Optional[Callable] = None       # (candidates, state, max_picks) -> [BetCandidate]
    fair_probs: Optional[Callable] = None         # (odds sequence) -> fair probabilities
    players: Optional[Callable] = None            # (fixture) -> [PlayerCandidate]
    strategies: tuple = ()
    # Tips ("pronostici probabili"): every piece optional, missing ones degrade gracefully.
    matrix: Optional[Callable] = None             # (fixture) -> score matrix [[p(h,a)]]
    tips: Optional[Callable] = None               # (fixture, matrix) -> [Tip]
    tip_quotes: Optional[Callable] = None         # (fixtures) -> {fixture_id: {key: TipQuote}}
    select_tips: Optional[Callable] = None        # (tips_by_fixture, quotes, min_prob=, top_n=) -> [SelectedTip]
    multiples: Optional[Callable] = None          # (selected) -> [Multiple]


def build_default_deps(ledger_path: Optional[str] = None) -> Deps:
    """Wire the real modules (imports are lazy: integration owned by the supervisor)."""
    from core import contracts, devig, market_data, predictor, value_engine
    from core.ledger import Ledger

    async def players(fixture) -> List[Any]:
        from adapters.football_api import FootballAPIClient
        from analyzers.player_cards_analyzer import PlayerCardsAnalyzer
        from core import player_candidates, referee
        client = FootballAPIClient()
        loader = PlayerCardsAnalyzer()._load_roster
        ids = (fixture.home_id, fixture.away_id)
        squads = {t: await loader(client, t, fixture.season) for t in ids}
        xi = {t: await market_data.get_probable_xi(t, fixture.season, 3) for t in ids}
        lineups = await market_data.get_lineups(fixture.fixture_id)
        strict = referee.strictness(fixture.referee, fixture.kickoff) if fixture.referee else 1.0
        return player_candidates.rank_booking_candidates(
            fixture, squads, xi, referee_strictness=strict, official_lineups=lineups, top_n=10)

    tips_wiring = _tips_wiring()
    return Deps(
        **tips_wiring,
        ledger=Ledger(ledger_path) if ledger_path else Ledger(), league_id=serie_a_league_id(),
        refresh=market_data.refresh_current_season_data,
        upcoming=market_data.get_upcoming_fixtures, prices=market_data.get_prices,
        benchmark=market_data.get_benchmark_prices, result=market_data.get_result,
        predict=predictor.predict_fixture, build_candidates=value_engine.build_candidates,
        select_daily=value_engine.select_daily, fair_probs=devig.shin, players=players,
        strategies=contracts.STRATEGIES,
    )


def _tips_wiring() -> Dict[str, Any]:
    """Real tip modules, imported lazily: each one still missing simply stays None."""
    wiring: Dict[str, Any] = {}
    for name, module, attr in (("matrix", "core.predictor", "predict_matrix"),
                               ("tips", "core.tips", "tips_for_fixture"),
                               ("tip_quotes", "core.market_tips", "collect_tip_quotes"),
                               ("select_tips", "core.tip_selection", "select_daily_tips"),
                               ("multiples", "core.tip_selection", "build_multiples")):
        try:
            wiring[name] = getattr(importlib.import_module(module), attr)
        except (ImportError, AttributeError):
            wiring[name] = None
    return wiring
