"""Tests for the bankroll simulation and fuzzy team matching."""

from backtest.bankroll import _norm, build_fuzzy_index, simulate


def test_fuzzy_matches_name_variants():
    our = ["AC Milan", "Inter", "Hellas Verona", "AS Roma"]
    records = [
        {"home": "Milan", "away": "Inter", "o1": 2.0},
        {"home": "Verona", "away": "Roma", "o1": 3.0},
    ]
    index, unmatched = build_fuzzy_index(records, our)
    assert not unmatched
    assert ("AC Milan", "Inter") in index
    assert ("Hellas Verona", "AS Roma") in index


def test_norm_lowercases_and_strips_accents():
    assert _norm("AC Milan") == "ac milan"
    assert _norm("Atlético Madrid") == "atletico madrid"   # accents removed
    assert _norm("Real Betis") == "real betis"


def _pred(home, away, hg, ag, p1, pX, p2, pover):
    return {
        "home_name": home, "away_name": away, "home_goals": hg, "away_goals": ag,
        "probs": {"result_1": p1, "result_X": pX, "result_2": p2, "over_2_5": pover},
    }


def test_winning_value_bet_grows_bankroll():
    preds = [_pred("A", "B", 2, 0, 0.70, 0.20, 0.10, 0.5)]
    odds = {("A", "B"): {"o1": 2.0, "ox": 4.0, "o2": 5.0, "oover": 2.0, "ounder": 2.0}}
    sim = simulate(preds, odds, start=100.0, edge_threshold=0.05)
    # our 70% on home at odds 2.0 (implied 50%) is a big value bet; home won.
    assert sim["n_bets"] >= 1
    assert sim["final"] > 100.0


def test_losing_bet_shrinks_bankroll():
    preds = [_pred("A", "B", 0, 2, 0.70, 0.20, 0.10, 0.3)]
    odds = {("A", "B"): {"o1": 2.0, "ox": 4.0, "o2": 5.0, "oover": 2.0, "ounder": 2.0}}
    sim = simulate(preds, odds, start=100.0, edge_threshold=0.05)
    assert sim["final"] < 100.0


def test_no_value_no_bets():
    # model agrees with the (vig-free) market -> no edge -> no bets.
    preds = [_pred("A", "B", 1, 1, 0.33, 0.34, 0.33, 0.5)]
    odds = {("A", "B"): {"o1": 3.0, "ox": 3.0, "o2": 3.0, "oover": 2.0, "ounder": 2.0}}
    sim = simulate(preds, odds, start=100.0, edge_threshold=0.05)
    assert sim["n_bets"] == 0
    assert sim["final"] == 100.0
