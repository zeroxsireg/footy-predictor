"""
Serialise prediction cards to clean, versioned JSON — the data contract the
frontend consumes. Separates the model ("brain") from the presentation ("face").
"""

import json
import os
from datetime import datetime, timezone
from typing import Dict, List, Tuple

LEAGUE_NAMES = {135: "Serie A", 140: "La Liga", 39: "Premier League", 78: "Bundesliga"}
SCHEMA_VERSION = 1
DEFAULT_OUT = "predictions"


def _r(x: float) -> float:
    return round(x, 3)


def card_to_json(card: Dict) -> Dict:
    """Transform an internal card dict into the public JSON structure."""
    g = card["goals"]
    markets = {
        "1x2": {"home": _r(g["result_1"]), "draw": _r(g["result_X"]), "away": _r(g["result_2"])},
        "goals": {
            "over_1_5": _r(g["over_1_5"]), "over_2_5": _r(g["over_2_5"]),
            "over_3_5": _r(g["over_3_5"]), "btts": _r(g["btts_yes"]),
        },
        "multigol": {
            "1-2": _r(g["mg_total_1_2"]), "2-3": _r(g["mg_total_2_3"]),
            "1-3": _r(g["mg_total_1_3"]), "2-4": _r(g["mg_total_2_4"]),
            "home_1-3": _r(g["mg_home_1_3"]), "away_1-3": _r(g["mg_away_1_3"]),
        },
        "cards": None,
        "players_at_risk": None,
    }
    if card.get("cards"):
        cc = card["cards"]
        markets["cards"] = {
            "expected": round(cc["expected"], 2),
            "over_3_5": _r(cc["over"][3.5]), "over_4_5": _r(cc["over"][4.5]),
            "over_5_5": _r(cc["over"][5.5]),
        }
    if card.get("players"):
        home_id = card.get("home_id")
        away_id = card.get("away_id")
        markets["players_at_risk"] = [
            {
                "name": p["name"],
                "team": "home" if p.get("team_id") is not None and p.get("team_id") == home_id else "away" if p.get("team_id") is not None and p.get("team_id") == away_id else None,
                "position": p["position"],
                "prob": _r(p["prob"])
            }
            for p in card["players"]
        ]

    result = None
    a = card.get("actual") or {}
    if a.get("home_goals") is not None:
        result = {"home_goals": a["home_goals"], "away_goals": a["away_goals"]}

    return {
        "fixture_id": card.get("fixture_id"),
        "home": card["home"], "away": card["away"],
        "date": card.get("date"), "referee": card.get("referee"),
        "markets": markets,
        "result": result,
    }


def round_document(league_id: int, season: int, matchday: int, cards: List[Dict]) -> Dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "league": {"id": league_id, "name": LEAGUE_NAMES.get(league_id, str(league_id))},
        "season": season,
        "matchday": matchday,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "matches": [card_to_json(c) for c in cards],
    }


def export_round(
    league_id: int, *, season: int, history_seasons: List[int], matchday: int,
    out_dir: str = DEFAULT_OUT,
) -> Tuple[str, int]:
    """Predict a round and write its JSON. Returns (path, n_matches)."""
    from backtest.card import predict_round
    cards = predict_round(league_id, season=season, history_seasons=history_seasons,
                          round_name=f"Regular Season - {matchday}")
    doc = round_document(league_id, season, matchday, cards)
    path = os.path.join(out_dir, f"league_{league_id}", f"season_{season}",
                        f"round_{matchday}.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, ensure_ascii=False)
    return path, len(cards)
