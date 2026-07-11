"""Smoke test for the prediction card (uses real cache if present)."""

import os

import pytest

from backtest.card import build_prediction_card, find_fixture_id
from backtest.data import cache_path

_SERIE_A_2024 = cache_path(135, 2024)


@pytest.mark.skipif(not os.path.exists(_SERIE_A_2024), reason="Serie A cache not present")
def test_build_card_on_real_fixture():
    fid = find_fixture_id(135, 2024, "Inter", "AC Milan")
    assert fid is not None

    card = build_prediction_card(135, fid, season=2024, history_seasons=[2023])
    assert card is not None
    g = card["goals"]
    assert g is not None
    # 1X2 is a distribution
    assert abs(g["result_1"] + g["result_X"] + g["result_2"] - 1.0) < 1e-6
    # multigol keys present
    assert "mg_total_1_3" in g and 0.0 <= g["mg_total_1_3"] <= 1.0
    # Serie A has card data -> team cards + at-risk players present
    assert card["cards"] is not None
    assert card["cards"]["expected"] > 0
    assert card["players"] and len(card["players"]) <= 6
    # at-risk players are sorted by descending probability
    probs = [p["prob"] for p in card["players"]]
    assert probs == sorted(probs, reverse=True)
    # actual result available for the demo comparison
    assert card["actual"]["home_goals"] is not None


def test_find_fixture_id_missing_returns_none():
    assert find_fixture_id(135, 2024, "Nonexistent United", "Ghost FC") is None


@pytest.mark.skipif(not os.path.exists(_SERIE_A_2024), reason="Serie A cache not present")
def test_predict_upcoming_produces_forward_card():
    from backtest.card import predict_upcoming
    # Predict a mid-season matchup as-of an early-season cutoff (only prior data).
    card = predict_upcoming(135, "Inter", "AC Milan",
                            season=2024, history_seasons=[2023], as_of_date="2025-01-01")
    assert card is not None and card["upcoming"] is True
    assert card["goals"] is not None
    g = card["goals"]
    assert abs(g["result_1"] + g["result_X"] + g["result_2"] - 1.0) < 1e-6
    assert card["cards"] is not None            # Serie A
    assert card["players"]                       # expected-lineup at-risk players


@pytest.mark.skipif(not os.path.exists(_SERIE_A_2024), reason="Serie A cache not present")
def test_predict_round_returns_all_matches():
    from backtest.card import predict_round
    cards = predict_round(135, season=2024, history_seasons=[2023],
                          round_name="Regular Season - 20")
    assert len(cards) >= 8                        # a full Serie A round
    assert all(c["goals"] is not None for c in cards)
