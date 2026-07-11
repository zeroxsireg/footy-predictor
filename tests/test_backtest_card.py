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
