"""Tests for the bankroll simulation and fuzzy team matching."""

from backtest.bankroll import _norm, build_fuzzy_index, simulate
from backtest.odds_data import LEAGUE_ALIASES, parse_odds


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
    sim = simulate(preds, odds, start=100.0, ev_threshold=0.05)
    # our 70% on home at odds 2.0 (implied 50%) is a big value bet; home won.
    assert sim["n_bets"] >= 1
    assert sim["final"] > 100.0


def test_losing_bet_shrinks_bankroll():
    preds = [_pred("A", "B", 0, 2, 0.70, 0.20, 0.10, 0.3)]
    odds = {("A", "B"): {"o1": 2.0, "ox": 4.0, "o2": 5.0, "oover": 2.0, "ounder": 2.0}}
    sim = simulate(preds, odds, start=100.0, ev_threshold=0.05)
    assert sim["final"] < 100.0


def test_no_value_no_bets():
    # model agrees with the (vig-free) market -> no edge -> no bets.
    preds = [_pred("A", "B", 1, 1, 0.33, 0.34, 0.33, 0.5)]
    odds = {("A", "B"): {"o1": 3.0, "ox": 3.0, "o2": 3.0, "oover": 2.0, "ounder": 2.0}}
    sim = simulate(preds, odds, start=100.0, ev_threshold=0.05)
    assert sim["n_bets"] == 0
    assert sim["final"] == 100.0


# ── La Liga name matching regression (A) ─────────────────────────────────────

LIGA_NAMES = ["Real Madrid", "Atletico Madrid", "Athletic Club", "Barcelona"]


def _fx(home, away, hg, ag, date="2025-09-01T18:00:00+00:00"):
    return {"home_name": home, "away_name": away, "home_goals": hg, "away_goals": ag,
            "date": date}


def test_alias_table_maps_ath_madrid_and_bilbao_correctly():
    csv_text = (
        "Date,HomeTeam,AwayTeam,FTHG,FTAG,B365CH,B365CD,B365CA\n"
        "01/09/2025,Ath Madrid,Ath Bilbao,2,1,1.8,3.5,4.5\n"
    )
    recs = parse_odds(csv_text, LEAGUE_ALIASES[140])
    index, unmatched = build_fuzzy_index(
        recs, LIGA_NAMES, fixtures=[_fx("Atletico Madrid", "Athletic Club", 2, 1)])
    assert not unmatched
    assert ("Atletico Madrid", "Athletic Club") in index
    assert not any("Real Madrid" in k for k in index)


def test_fuzzy_never_steals_a_name_claimed_by_exact_match():
    # Without an alias, "Ath Madrid" used to fuzzy-match to Real Madrid (cutoff 0.6).
    recs = [
        {"home": "Real Madrid", "away": "Barcelona", "fthg": 1, "ftag": 1, "o1": 2.0},
        {"home": "Ath Madrid", "away": "Barcelona", "fthg": 0, "ftag": 0, "o1": 3.0},
    ]
    index, unmatched = build_fuzzy_index(recs, ["Real Madrid", "Barcelona"])
    assert ("Real Madrid", "Barcelona") in index
    assert index[("Real Madrid", "Barcelona")]["o1"] == 2.0     # not overwritten
    assert unmatched == [("Ath Madrid", "Barcelona")]


def test_goal_cross_check_rejects_odds_of_another_match():
    recs = [{"home": "Real Madrid", "away": "Barcelona", "fthg": 0, "ftag": 0,
             "date": "01/09/2025", "o1": 2.0}]
    rejected = []
    index, unmatched = build_fuzzy_index(
        recs, LIGA_NAMES, fixtures=[_fx("Real Madrid", "Barcelona", 3, 1)], rejected=rejected)
    assert index == {}
    assert unmatched == [("Real Madrid", "Barcelona")]
    assert len(rejected) == 1


def test_simulate_uses_ev_rule_not_raw_edge():
    # p=0.23 @ 5.0: EV=+15% (> 5%) but raw edge (p - 1/odds) = +3% (< 5%).
    preds = [_pred("A", "B", 1, 0, 0.23, 0.40, 0.37, 0.5)]
    odds = {("A", "B"): {"o1": 5.0, "ox": 2.0, "o2": 2.0}}
    sim = simulate(preds, odds, ev_threshold=0.05, markets=("1x2",))
    assert sim["n_bets"] == 1
