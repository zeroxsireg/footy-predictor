"""
Value engine: the ONLY place where de-vig, EV and stake are computed (rules 6-8, 11).

Strategies (core/contracts.py), each with its own paper bankroll:
  raw        p_used = model probability.
  blend50    p_used = 0.5 * model + 0.5 * p_fair (Shin of the played bookmaker).
  sharp_gap  model-free: p_used = Shin p_fair of PINNACLE quotes of the same market,
             price played = Bet365 (EV = odds_bet365 * p_fair_pinnacle - 1).
             Pinnacle is only a yardstick, never a price to play.

CAVEAT: the model is on average WORSE than the market, so EV computed on the raw
model probability is optimistic. That is why blend50 and sharp_gap exist and why the
ledger compares the strategies on forward results.
"""

import math
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence

from .contracts import (MARKET_1X2, MARKET_OU25, STRATEGY_BLEND50, STRATEGY_RAW,
                        STRATEGY_SHARP_GAP, BetCandidate, MatchProbs, PriceQuote)
from .devig import shin
from .edge_calculator import KELLY_FRACTION, calculate_kelly
from .value_selection import (BREAKER_DRAWDOWN, BREAKER_KELLY_FRACTION, INITIAL_BANKROLL,
                              MAX_DAILY_FRACTION, MAX_DAILY_PICKS, MAX_STAKE_FRACTION,
                              MIN_EV_THRESHOLD, MIN_STAKE, STAKE_STEP, ev_fraction)

SELECTIONS = {MARKET_1X2: ("1", "X", "2"), MARKET_OU25: ("over", "under")}


@dataclass
class BankrollState:
    """Paper bankroll of one strategy. breaker_active is latched by the ledger."""
    bankroll: float = INITIAL_BANKROLL
    high_water_mark: float = INITIAL_BANKROLL
    breaker_active: bool = False

    @property
    def drawdown(self) -> float:
        if self.high_water_mark <= 0:
            return 0.0
        return max(0.0, (self.high_water_mark - self.bankroll) / self.high_water_mark)

    def after_update(self, new_bankroll: float) -> "BankrollState":
        """New state with high-water mark and latched breaker (off only at a new HWM)."""
        hwm = max(self.high_water_mark, new_bankroll)
        dd = (hwm - new_bankroll) / hwm if hwm > 0 else 0.0
        active = (self.breaker_active or dd > BREAKER_DRAWDOWN) and new_bankroll < hwm
        return BankrollState(new_bankroll, hwm, active)

    @property
    def kelly_multiplier(self) -> float:
        tripped = self.breaker_active or self.drawdown > BREAKER_DRAWDOWN
        return BREAKER_KELLY_FRACTION if tripped else KELLY_FRACTION


def _model_prob(probs: MatchProbs, market: str, selection: str) -> float:
    if market == MARKET_1X2:
        return {"1": probs.p1, "X": probs.px, "2": probs.p2}[selection]
    return probs.p_over_2_5 if selection == "over" else 1.0 - probs.p_over_2_5


def _fair(quote: Optional[PriceQuote], market: str) -> Optional[Dict[str, float]]:
    """Shin fair probabilities of a quote, or None if incomplete/invalid."""
    if quote is None:
        return None
    sels = SELECTIONS[market]
    try:
        odds = [quote.odds[s] for s in sels]
        return dict(zip(sels, shin(odds)))
    except (KeyError, ValueError, TypeError):
        return None


def build_candidates(fixture_id: int, probs: Optional[MatchProbs],
                     quotes: Dict[str, PriceQuote], benchmark: Dict[str, PriceQuote],
                     strategy: str, tau: float = MIN_EV_THRESHOLD) -> List[BetCandidate]:
    """All selections with EV >= tau for `strategy` (unsized). Quotes keyed by market."""
    if strategy not in (STRATEGY_RAW, STRATEGY_BLEND50, STRATEGY_SHARP_GAP):
        raise ValueError(f"unknown strategy {strategy}")
    if strategy != STRATEGY_SHARP_GAP and probs is None:
        return []
    now = datetime.now(timezone.utc)
    out: List[BetCandidate] = []
    for market, sels in SELECTIONS.items():
        quote = quotes.get(market)
        if quote is None or not quote.bookmaker:
            continue                                   # rule 11: real bookmaker only
        fair_book = _fair(quote, market)
        ref = _fair(benchmark.get(market), market) if strategy == STRATEGY_SHARP_GAP else fair_book
        if ref is None:
            continue
        for sel in sels:
            odds = quote.odds.get(sel)
            if odds is None or odds <= 1.0:
                continue
            p_model = _model_prob(probs, market, sel) if probs else float("nan")
            if strategy == STRATEGY_RAW:
                p_used = p_model
            elif strategy == STRATEGY_BLEND50:
                p_used = 0.5 * p_model + 0.5 * ref[sel]
            else:
                p_used = ref[sel]
            ev = ev_fraction(p_used, odds)
            if ev >= tau:
                out.append(BetCandidate(fixture_id, strategy, market, sel, odds, quote.bookmaker,
                                        p_model, p_used, ref[sel], ev, created_at=now))
    return out


def _round_stake(x: float) -> float:
    return round(round(x / STAKE_STEP) * STAKE_STEP, 2)


def _get(obj, name):
    return obj[name] if isinstance(obj, dict) else getattr(obj, name)


def select_daily(candidates: List[BetCandidate], state: BankrollState,
                 max_picks: int = MAX_DAILY_PICKS,
                 already_placed: Sequence = ()) -> List[BetCandidate]:
    """
    Best-EV singles for ONE strategy and ONE calendar day (caller groups by day).

    already_placed: bets already registered that day (dicts/objects with fixture_id, market,
    stake_amount): they reduce the residual pick count and the residual 12% budget, and
    their (fixture, market) is never chosen again.
    """
    placed = [b for b in already_placed if _get(b, "status") != "void"] \
        if already_placed and isinstance(already_placed[0], dict) and "status" in already_placed[0] \
        else list(already_placed)
    seen = {(_get(b, "fixture_id"), _get(b, "market")) for b in placed}
    room = min(max_picks, MAX_DAILY_PICKS) - len(placed)
    budget = MAX_DAILY_FRACTION * state.bankroll - sum(_get(b, "stake_amount") for b in placed)
    if room <= 0 or budget <= 0:
        return []
    chosen = []
    for c in sorted(candidates, key=lambda c: c.ev, reverse=True):
        key = (c.fixture_id, c.market)                 # one selection per market/fixture
        if key in seen or not c.bookmaker or c.odds <= 1.0:
            continue
        seen.add(key)
        chosen.append(c)
        if len(chosen) >= room:
            break
    mult = state.kelly_multiplier
    fracs = [min(mult * calculate_kelly(c.p_used, c.odds), MAX_STAKE_FRACTION) for c in chosen]
    total = sum(fracs)
    cap = budget / state.bankroll
    if total > cap:
        fracs = [f * cap / total for f in fracs]
    out = []
    for c, f in zip(chosen, fracs):
        amount = _round_stake(state.bankroll * f)
        if amount < MIN_STAKE - 1e-9 or math.isnan(amount):
            continue
        out.append(replace(c, stake_amount=amount, stake_fraction=amount / state.bankroll))
    return out
