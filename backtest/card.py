"""
Prediction card: unify every validated model into one structured forecast for a
single match (1X2, Over/Under, BTTS, multigol, team cards, at-risk players).

Built from the per-match generators, so the card shows EXACTLY the numbers the
backtests validated. Cards/players are only produced for leagues with the data
and the edge (Serie A, La Liga).
"""

from typing import Dict, List, Optional

from backtest.ablation import load_seasons
from backtest.data import cache_path  # noqa: F401
from backtest.xg_data import xg_cache_path, load_xg_map
from backtest.cards_data import cards_cache_path, load_cards_map
from backtest.player_data import players_cache_path, load_players_map
from backtest.xg_compare import iter_xg_predictions
from backtest.cards import iter_cards_predictions
from backtest.player_cards import iter_player_predictions

CARDS_LEAGUES = {135, 140}   # leagues with card data + edge


def _merge(loader, path_fn, league, seasons):
    m = {}
    for s in seasons:
        try:
            m.update(loader(path_fn(league, s)))
        except FileNotFoundError:
            pass
    return m


def build_prediction_card(
    league_id: int, target_fixture_id: int, *,
    season: int, history_seasons: List[int], k: float = 5.0,
) -> Optional[Dict]:
    seasons = history_seasons + [season]
    fixtures = load_seasons(league_id, seasons)
    target = next((f for f in fixtures if f["fixture_id"] == target_fixture_id), None)
    if target is None:
        return None

    card: Dict = {
        "league_id": league_id,
        "fixture_id": target_fixture_id,
        "home": target.get("home_name"),
        "away": target.get("away_name"),
        "date": target.get("date"),
        "referee": target.get("referee"),
        "actual": {"home_goals": target.get("home_goals"), "away_goals": target.get("away_goals")},
        "goals": None, "cards": None, "players": None,
    }

    # ── goals / 1X2 / BTTS / multigol (xG model) ──
    xg = _merge(load_xg_map, xg_cache_path, league_id, seasons)
    for pred in iter_xg_predictions(fixtures, xg, target_season=season, k=k):
        if pred["fixture_id"] == target_fixture_id:
            card["goals"] = pred["probs"]
            break

    if league_id not in CARDS_LEAGUES:
        return card

    # ── team cards ──
    cards_map = _merge(load_cards_map, cards_cache_path, league_id, seasons)
    for pred in iter_cards_predictions(fixtures, cards_map, score_seasons={season}):
        if pred["fixture_id"] == target_fixture_id:
            card["cards"] = {"expected": pred["expected"], "over": pred["over"]}
            break
    ac = cards_map.get(str(target_fixture_id))
    if ac:
        card["actual"]["total_cards"] = (ac.get("home_cards") or 0) + (ac.get("away_cards") or 0)

    # ── at-risk players ──
    players_map = _merge(load_players_map, players_cache_path, league_id, seasons)
    for pred in iter_player_predictions(fixtures, players_map, score_seasons={season}):
        if pred["fixture_id"] == target_fixture_id:
            ranked = sorted(pred["players"], key=lambda x: x["prob"], reverse=True)
            card["players"] = ranked[:6]
            break
    roster = players_map.get(str(target_fixture_id)) or []
    card["actual"]["booked"] = [
        p.get("name") for p in roster if (p.get("yellow") or 0) >= 1
    ]
    return card


def find_fixture_id(league_id: int, season: int, home_sub: str, away_sub: str) -> Optional[int]:
    """Locate a fixture id by (partial) home/away team names within a season."""
    for f in load_seasons(league_id, [season]):
        if (home_sub.lower() in (f.get("home_name") or "").lower()
                and away_sub.lower() in (f.get("away_name") or "").lower()):
            return f["fixture_id"]
    return None
