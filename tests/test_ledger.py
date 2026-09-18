from datetime import datetime, timezone

import pytest

from core.contracts import (MARKET_1X2, MARKET_OU25, BetCandidate, FixtureResult, MatchProbs,
                            PlayerCandidate, PriceQuote)
from core.ledger import Ledger

T = datetime(2026, 9, 18, tzinfo=timezone.utc)


@pytest.fixture
def led():
    return Ledger(":memory:")


def bet(sel="1", odds=2.0, stake=1.0, strat="raw", market=MARKET_1X2, fx=1):
    return BetCandidate(fx, strat, market, sel, odds, "Bet365", 0.6, 0.6, 0.5, 0.2,
                        stake_amount=stake, stake_fraction=0.02, created_at=T)


def res(h, a, fx=1):
    return FixtureResult(fx, "FT", h, a)


def test_record_bets_idempotent(led):
    assert led.record_bets([bet()]) == 1
    assert led.record_bets([bet()]) == 0
    assert led.open_fixtures() == [1]


def test_settle_win_updates_bankroll_and_hwm(led):
    led.record_bets([bet(odds=2.5, stake=2.0)])
    led.settle_fixture(res(2, 0))
    st = led.bankroll_state("raw")
    assert st.bankroll == pytest.approx(53.0) and st.high_water_mark == pytest.approx(53.0)
    assert led.open_fixtures() == []
    s = led.stats("raw")
    assert s["n_bets"] == 1 and s["roi"] == pytest.approx(1.5) and s["hit_rate"] == 1.0


def test_settle_loss_and_ou(led):
    led.record_bets([bet("2", stake=1.0), bet("over", 1.9, 1.0, market=MARKET_OU25),
                     bet("under", 1.9, 1.0, market=MARKET_OU25)])
    led.settle_fixture(res(1, 1))
    st = led.bankroll_state("raw")
    assert st.bankroll == pytest.approx(50 - 1 - 1 + 0.9)      # 2 lost, over lost, under won
    assert st.high_water_mark == 50.0


def test_not_finished_not_settled(led):
    led.record_bets([bet()])
    assert led.settle_fixture(FixtureResult(1, "NS", None, None)) == 0
    assert led.open_fixtures() == [1]


def test_clv_uses_same_bookmaker_close(led):
    led.record_bets([bet(odds=2.2, stake=1.0)])
    led.record_closing(1, {MARKET_1X2: PriceQuote(1, MARKET_1X2, "Bet365", 8,
                       {"1": 2.0, "X": 3.5, "2": 4.0}, T)}, {})
    led.record_closing(1, {MARKET_1X2: PriceQuote(1, MARKET_1X2, "Bwin", 6,
                       {"1": 9.0, "X": 9.0, "2": 9.0}, T)}, {})
    led.settle_fixture(res(1, 0))
    row = led.conn.execute("SELECT closing_odds, clv FROM ledger_bets").fetchone()
    assert row["closing_odds"] == 2.0
    from core.devig import shin
    assert row["clv"] == pytest.approx(2.2 * shin([2.0, 3.5, 4.0])[0] - 1)


def test_drawdown_breaker_from_ledger(led):
    led.record_bets([bet(stake=15.0, fx=1), bet(stake=15.0, fx=2)])
    led.settle_fixture(res(0, 1, fx=1))
    led.settle_fixture(res(0, 1, fx=2))
    st = led.bankroll_state("raw")
    assert st.bankroll == 20.0 and st.high_water_mark == 50.0 and st.breaker_active
    assert led.stats("raw")["max_drawdown"] == pytest.approx(0.6)


def test_strategies_have_separate_bankrolls(led):
    led.record_bets([bet(strat="raw", stake=5.0), bet(strat="blend50", stake=5.0)])
    led.settle_fixture(res(0, 1))
    led.record_bets([bet(strat="raw", stake=1, fx=2)])
    assert led.bankroll_state("sharp_gap").bankroll == 50.0
    assert led.bankroll_state("blend50").bankroll == 45.0


def test_calibration_model_vs_market(led):
    led.record_predictions([MatchProbs(1, 0.6, 0.25, 0.15, 0.7, "m")])
    led.record_closing(1, {MARKET_1X2: PriceQuote(1, MARKET_1X2, "Bet365", 8, {"1": 2.0, "X": 3.5, "2": 4.0}, T),
                           MARKET_OU25: PriceQuote(1, MARKET_OU25, "Bet365", 8, {"over": 1.9, "under": 1.9}, T)}, {})
    assert 1 in led.unsettled_fixtures()
    led.settle_fixture(res(2, 1))
    c = led.calibration()
    assert c["n_1x2"] == 1 and c["n_ou25"] == 1
    assert c["brier_over_model"] == pytest.approx(0.09)
    assert c["brier_over_market"] == pytest.approx(0.25)
    assert c["rps_model"] < c["rps_market"]
    assert 1 not in led.unsettled_fixtures()


def test_players(led):
    led.record_player_predictions([PlayerCandidate(1, i, f"P{i}", "T", "D", 0.3, 1.0, p) for i, p in
                                   [(10, 0.4), (11, 0.3), (12, 0.1)]])
    led.settle_players(1, [10, 12])
    p = led.calibration(k=2)["players"]
    assert p["n"] == 3 and p["precision_at_k"] == 0.5
    assert p["brier"] == pytest.approx(((0.6) ** 2 + 0.3 ** 2 + 0.9 ** 2) / 3)


def test_max_drawdown_measured_from_peak(led):
    led.record_bets([bet(odds=3.0, stake=10.0, fx=1), bet(stake=10.0, fx=2)])
    led.settle_fixture(res(1, 0, fx=1))          # +20 -> 70
    led.settle_fixture(res(0, 1, fx=2))          # -10 -> 60
    assert led.stats("raw")["max_drawdown"] == pytest.approx(10 / 70)


def _close(book, odds, bid=8):
    return {MARKET_1X2: PriceQuote(1, MARKET_1X2, book, bid, odds, T)}


def test_clv_numeric_value(led):
    from core.devig import shin
    led.record_bets([bet(odds=2.5, stake=1.0)])
    led.record_closing(1, _close("Bet365", {"1": 2.2, "X": 3.4, "2": 3.6}), {})
    led.settle_fixture(res(1, 0))
    row = led.conn.execute("SELECT closing_odds, clv FROM ledger_bets").fetchone()
    assert row["closing_odds"] == 2.2
    assert row["clv"] == pytest.approx(2.5 * shin([2.2, 3.4, 3.6])[0] - 1, abs=1e-4)
    assert row["clv"] == pytest.approx(0.11249, abs=1e-4)


def test_clv_ignores_other_bookmaker(led):
    led.record_bets([bet(odds=2.5, stake=1.0)])
    led.record_closing(1, _close("Bwin", {"1": 2.2, "X": 3.4, "2": 3.6}, 6), {})
    led.settle_fixture(res(1, 0))
    row = led.conn.execute("SELECT closing_odds, clv FROM ledger_bets").fetchone()
    assert row["clv"] is None and row["closing_odds"] is None


def test_bets_for_fixtures(led):
    led.record_bets([bet(fx=1, stake=1.5), bet(fx=2, stake=2.0), bet(fx=3, strat="blend50")])
    rows = led.bets_for_fixtures("raw", [1, 2])
    assert sorted((r["fixture_id"], r["stake_amount"]) for r in rows) == [(1, 1.5), (2, 2.0)]
    assert led.bets_for_fixtures("raw", []) == []


def test_null_p_model_ignored_by_stats_and_calibration(led):
    b = bet(strat="sharp_gap", stake=1.0)
    b.p_model = float("nan")
    led.record_bets([b])
    assert led.conn.execute("SELECT p_model FROM ledger_bets").fetchone()[0] is None
    led.settle_fixture(res(1, 0))
    assert led.stats("sharp_gap")["n_bets"] == 1
    assert led.calibration()["n_1x2"] == 0
