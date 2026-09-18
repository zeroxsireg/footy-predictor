from datetime import datetime, timezone

import pytest

from core.contracts import (MARKET_1X2, MARKET_OU25, STRATEGY_BLEND50, STRATEGY_RAW,
                            STRATEGY_SHARP_GAP, BetCandidate, MatchProbs, PriceQuote)
from core.value_engine import BankrollState, build_candidates, select_daily

T = datetime(2026, 9, 18, tzinfo=timezone.utc)


def q(market, odds, book="Bet365", fx=1):
    return PriceQuote(fx, market, book, 8, odds, T)


PROBS = MatchProbs(1, 0.55, 0.25, 0.20, 0.5, "m")
BET365 = {MARKET_1X2: q(MARKET_1X2, {"1": 2.10, "X": 3.4, "2": 3.6})}
PINN = {MARKET_1X2: q(MARKET_1X2, {"1": 1.80, "X": 3.9, "2": 4.6}, "Pinnacle")}


def cand(fx, market, sel, ev, odds=2.5, p=0.5):
    return BetCandidate(fx, "raw", market, sel, odds, "Bet365", p, p, p, ev)


def test_raw_ev_and_threshold():
    c = build_candidates(1, PROBS, BET365, {}, STRATEGY_RAW)
    assert [x.selection for x in c] == ["1"]
    assert c[0].ev == pytest.approx(0.55 * 2.10 - 1, abs=1e-4)
    assert c[0].bookmaker == "Bet365"


def test_blend_uses_half_market():
    c = build_candidates(1, PROBS, BET365, {}, STRATEGY_BLEND50)
    raw = build_candidates(1, PROBS, BET365, {}, STRATEGY_RAW)
    if c:
        assert c[0].p_used == pytest.approx(0.5 * 0.55 + 0.5 * c[0].p_fair)
    assert not c or c[0].ev < raw[0].ev


def test_sharp_gap_plays_bet365_with_pinnacle_fair():
    c = build_candidates(1, None, BET365, PINN, STRATEGY_SHARP_GAP)
    assert c and c[0].selection == "1"
    assert c[0].odds == 2.10 and c[0].bookmaker == "Bet365"
    assert c[0].ev == pytest.approx(2.10 * c[0].p_fair - 1, abs=1e-4)
    assert build_candidates(1, None, BET365, {}, STRATEGY_SHARP_GAP) == []


def test_no_probs_no_raw_and_no_bookmaker_no_candidate():
    assert build_candidates(1, None, BET365, {}, STRATEGY_RAW) == []
    nb = {MARKET_1X2: q(MARKET_1X2, {"1": 2.10, "X": 3.4, "2": 3.6}, book="")}
    assert build_candidates(1, PROBS, nb, {}, STRATEGY_RAW) == []


def test_one_selection_per_market_and_max_three():
    cs = [cand(1, MARKET_1X2, "1", 0.10), cand(1, MARKET_1X2, "X", 0.09),
          cand(2, MARKET_1X2, "1", 0.08), cand(3, MARKET_1X2, "2", 0.07),
          cand(4, MARKET_1X2, "2", 0.06)]
    out = select_daily(cs, BankrollState())
    assert [(c.fixture_id, c.selection) for c in out] == [(1, "1"), (2, "1"), (3, "2")]


def test_kelly_quarter_cap_and_rounding():
    big = cand(1, MARKET_1X2, "1", 0.5, odds=3.0, p=0.5)     # f* = 0.25 -> quarter 6% -> cap 2.5%
    out = select_daily([big], BankrollState(100, 100))
    assert out[0].stake_amount == 2.5
    assert out[0].stake_fraction == pytest.approx(0.025)


def test_daily_cap_scales_and_tiny_stake_dropped():
    cs = [cand(i, MARKET_1X2, "1", 0.5, odds=3.0) for i in range(1, 4)]   # 3 x 2.5% = 7.5% < 12%
    assert sum(c.stake_amount for c in select_daily(cs, BankrollState(100, 100))) == 7.5
    tiny = cand(1, MARKET_1X2, "1", 0.031, odds=2.0, p=0.5155)
    assert select_daily([tiny], BankrollState(5, 5)) == []


def test_daily_cap_binds_with_bigger_cap(monkeypatch):
    import core.value_engine as ve
    monkeypatch.setattr(ve, "MAX_DAILY_FRACTION", 0.06)
    cs = [cand(i, MARKET_1X2, "1", 0.5, odds=3.0) for i in range(1, 4)]
    tot = sum(c.stake_amount for c in select_daily(cs, BankrollState(100, 100)))
    assert tot == pytest.approx(6.0, abs=0.1)


def test_circuit_breaker_halves_kelly():
    c = cand(1, MARKET_1X2, "1", 0.02, odds=2.0, p=0.52)     # f*=0.04 -> 0.01 / 0.005
    normal = select_daily([c], BankrollState(1000, 1000))[0].stake_amount
    dd = select_daily([c], BankrollState(700, 1000))[0].stake_amount
    assert normal == 10.0 and dd == pytest.approx(0.125 / 0.25 * normal * 0.7, abs=0.05)


def test_breaker_latches_until_high_water_mark():
    st = BankrollState(100, 100).after_update(75)            # dd 25% -> trips
    assert st.breaker_active
    st = st.after_update(90)                                 # dd 10% but not recovered
    assert st.breaker_active and st.kelly_multiplier == 0.125
    st = st.after_update(100)
    assert not st.breaker_active and st.kelly_multiplier == 0.25


def placed(fx, stake, market=MARKET_1X2, status="open"):
    return {"fixture_id": fx, "market": market, "selection": "1", "stake_amount": stake, "status": status}


def test_already_placed_reduces_picks():
    cs = [cand(i, MARKET_1X2, "1", 0.5, odds=3.0) for i in range(3, 7)]
    out = select_daily(cs, BankrollState(100, 100), already_placed=[placed(1, 1.0), placed(2, 1.0)])
    assert len(out) == 1
    assert select_daily(cs, BankrollState(100, 100),
                        already_placed=[placed(1, 1), placed(2, 1), placed(9, 1)]) == []


def test_already_placed_reduces_daily_budget():
    cs = [cand(i, MARKET_1X2, "1", 0.5, odds=3.0) for i in range(3, 5)]      # 2 x 2.5 = 5.0
    out = select_daily(cs, BankrollState(100, 100), already_placed=[placed(1, 9.0)])
    assert sum(c.stake_amount for c in out) <= 3.0 + 1e-9 and out
    assert select_daily(cs, BankrollState(100, 100), already_placed=[placed(1, 12.0)]) == []


def test_days_are_independent():
    cs = [cand(i, MARKET_1X2, "1", 0.5, odds=3.0) for i in range(1, 4)]
    day2 = [cand(i, MARKET_1X2, "1", 0.5, odds=3.0) for i in range(11, 14)]
    st = BankrollState(100, 100)
    assert len(select_daily(cs, st)) == 3 and len(select_daily(day2, st)) == 3


def test_already_placed_same_fixture_market_not_repeated():
    out = select_daily([cand(1, MARKET_1X2, "X", 0.5, odds=3.0)], BankrollState(100, 100),
                       already_placed=[placed(1, 1.0)])
    assert out == []
