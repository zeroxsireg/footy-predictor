"""Tests for the JSON export (data contract)."""

from backtest.export import card_to_json, round_document, SCHEMA_VERSION


def _card():
    g = {
        "result_1": 0.5, "result_X": 0.3, "result_2": 0.2,
        "over_1_5": 0.8, "over_2_5": 0.55, "over_3_5": 0.3, "btts_yes": 0.58,
        "mg_total_1_2": 0.34, "mg_total_2_3": 0.43, "mg_total_1_3": 0.56,
        "mg_total_2_4": 0.61, "mg_home_1_3": 0.72, "mg_away_1_3": 0.64,
    }
    return {
        "fixture_id": 42, "home": "Inter", "away": "AC Milan",
        "date": "2025-01-01T20:45:00Z", "referee": "M. Guida",
        "goals": g,
        "cards": {"expected": 4.2, "over": {3.5: 0.6, 4.5: 0.4, 5.5: 0.2}},
        "players": [{"name": "Bastoni", "position": "D", "prob": 0.28}],
        "actual": {"home_goals": 1, "away_goals": 2},
    }


def test_card_to_json_structure():
    j = card_to_json(_card())
    assert j["home"] == "Inter" and j["fixture_id"] == 42
    m = j["markets"]
    assert m["1x2"] == {"home": 0.5, "draw": 0.3, "away": 0.2}
    assert m["goals"]["over_2_5"] == 0.55 and m["goals"]["btts"] == 0.58
    assert set(m["multigol"]) == {"1-2", "2-3", "1-3", "2-4", "home_1-3", "away_1-3"}
    assert m["cards"]["expected"] == 4.2 and m["cards"]["over_4_5"] == 0.4
    assert m["players_at_risk"][0] == {"name": "Bastoni", "position": "D", "prob": 0.28}
    assert j["result"] == {"home_goals": 1, "away_goals": 2}


def test_card_to_json_without_cards_players():
    card = _card()
    card["cards"] = None
    card["players"] = None
    card["actual"] = {"home_goals": None, "away_goals": None}
    j = card_to_json(card)
    assert j["markets"]["cards"] is None
    assert j["markets"]["players_at_risk"] is None
    assert j["result"] is None            # upcoming match, no result yet


def test_round_document_wraps_matches():
    doc = round_document(135, 2024, 20, [_card(), _card()])
    assert doc["schema_version"] == SCHEMA_VERSION
    assert doc["league"] == {"id": 135, "name": "Serie A"}
    assert doc["matchday"] == 20 and len(doc["matches"]) == 2
    assert "generated_at" in doc
