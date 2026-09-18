"""Tests for the shared player booking model (core/player_card_model.py)."""

import pytest

from core.player_card_model import (
    LIVE_POSITION_PRIORS, PlayerCardModel, PlayerStat, live_probability,
    normalize_position, player_rate, P_CLAMP,
)


def _pl(pid, pos="D", yellow=0, fouls=None, minutes=90, team=1):
    return {"player_id": pid, "name": f"P{pid}", "team_id": team, "position": pos,
            "minutes": minutes, "yellow": yellow, "fouls": fouls}


def test_few_apps_shrink_toward_position_prior():
    # 3 yellows in 3 apps must NOT read as ~100%: it collapses toward the prior.
    p = live_probability(3, 3, "Defender")
    assert p is not None
    assert LIVE_POSITION_PRIORS["D"] < p < 0.30


def test_more_evidence_moves_estimate_away_from_prior():
    few = live_probability(3, 3, "D")
    many = live_probability(60, 60 * 0.5, "D")
    assert many > few


def test_goalkeepers_and_unknown_positions_excluded():
    assert live_probability(20, 2, "Goalkeeper") is None
    assert live_probability(20, 2, "G") is None
    assert live_probability(20, 2, "???") is None
    assert live_probability(0, 0, "D") is None


def test_position_ordering_defender_above_forward():
    assert live_probability(10, 1, "D") > live_probability(10, 1, "F")


def test_probability_is_clamped():
    p = live_probability(1000, 1000, "D", fouls=50000)
    assert p == pytest.approx(P_CLAMP[1])


def test_normalize_position():
    assert normalize_position("Centre-Back") == "D"
    assert normalize_position("Attacker") == "F"
    assert normalize_position(None) == "?"


def test_player_rate_pure_shrinkage_formula():
    assert player_rate(PlayerStat(apps=6, yellows=3), 0.1) == pytest.approx((3 + 64 * 0.1) / (6 + 64))


def test_point_in_time_current_match_label_does_not_change_prediction():
    def probs(current_yellow):
        m = PlayerCardModel()
        for _ in range(5):
            m.update_match([_pl(1, yellow=1), _pl(2), _pl(3, "F")], "R")
        rows = m.predict_match([_pl(1, yellow=current_yellow), _pl(2), _pl(3, "F")], "R")
        return [r["prob"] for r in rows]
    assert probs(0) == probs(1)   # the outcome of match N never leaks into its own forecast


def test_model_skips_keepers_and_unseen_players():
    m = PlayerCardModel()
    for _ in range(4):
        m.update_match([_pl(1, "G"), _pl(2, "D")], "R")
    rows = m.predict_match([_pl(1, "G"), _pl(2, "D"), _pl(99, "D")], "R")
    assert [r["player_id"] for r in rows] == [2]


def test_habitual_booker_scores_higher_and_backtest_uses_same_model():
    from backtest.player_cards import iter_player_predictions
    fixtures, pmap = [], {}
    for i in range(1, 15):
        fixtures.append({"fixture_id": i, "date": f"2024-01-{i:02d}", "status": "FT",
                         "season": 2024, "referee": "R"})
        pmap[str(i)] = [_pl(1, yellow=1 if i % 2 else 0), _pl(2), _pl(3), _pl(4)]
    preds = list(iter_player_predictions(fixtures, pmap, min_apps=3, k=8.0))
    last = {r["player_id"]: r["prob"] for r in preds[-1]["players"]}
    assert last[1] > last[2]
    # identical to driving the shared model directly (SSOT)
    from core.player_card_model import CardModelParams
    m = PlayerCardModel(CardModelParams(k=8.0, min_apps=3))
    expected = None
    for f in fixtures:
        played = pmap[str(f["fixture_id"])]
        expected = m.predict_match(played, "R")
        m.update_match(played, "R")
    assert {r["player_id"]: r["prob"] for r in expected} == last
