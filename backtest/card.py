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


# ── forward prediction (matches not yet played) ──────────────────────────────

_SYNTH_FID = -999  # sentinel id for the match-to-predict


def _find_team(fixtures: List[Dict], name_sub: str):
    """Resolve a (partial) team name to (team_id, canonical_name)."""
    n = name_sub.lower()
    for f in fixtures:
        if n in (f.get("home_name") or "").lower():
            return f["home_id"], f["home_name"]
        if n in (f.get("away_name") or "").lower():
            return f["away_id"], f["away_name"]
    return None, None


def _expected_roster(players_map, fixtures, team_id, before_date, synth_fid):
    """Proxy expected lineup = the team's most recent completed roster."""
    played = sorted(
        [f for f in fixtures if f.get("status") == "FT"
         and str(f["fixture_id"]) in players_map
         and (before_date is None or f["date"] < before_date)
         and team_id in (f["home_id"], f["away_id"])],
        key=lambda f: f["date"], reverse=True,
    )
    if not played:
        return []
    roster = players_map[str(played[0]["fixture_id"])]
    out = []
    for p in roster:
        if p.get("team_id") == team_id and p.get("minutes"):
            out.append({**p, "minutes": 90, "yellow": 0})  # future match: no card yet
    return out


def predict_upcoming(
    league_id: int, home_sub: str, away_sub: str, *,
    season: int, history_seasons: List[int], as_of_date: Optional[str] = None,
    referee: Optional[str] = None, k: float = 5.0,
) -> Optional[Dict]:
    """
    Predict a match that has NOT been played, using only data available before
    `as_of_date` (or all cached data, for a genuinely future match).

    Uses a synthetic fixture appended to the timeline so the validated
    generators produce its prediction from the final model state.
    """
    seasons = history_seasons + [season]
    all_fixtures = load_seasons(league_id, seasons)
    completed = [f for f in all_fixtures
                 if as_of_date is None or f["date"] < as_of_date]
    if not completed:
        return None

    home_id, home_name = _find_team(all_fixtures, home_sub)
    away_id, away_name = _find_team(all_fixtures, away_sub)
    if home_id is None or away_id is None:
        return None

    cutoff = as_of_date or max(f["date"] for f in completed)
    synth = {
        "fixture_id": _SYNTH_FID, "date": cutoff[:10] + "T23:59:59Z", "status": "FT",
        "season": season, "home_id": home_id, "away_id": away_id,
        "home_name": home_name, "away_name": away_name, "referee": referee,
        "home_goals": 0, "away_goals": 0,   # dummy; ignored (synthetic is last)
    }
    fixtures = completed + [synth]

    card: Dict = {
        "league_id": league_id, "home": home_name, "away": away_name,
        "date": synth["date"], "referee": referee, "upcoming": True,
        "goals": None, "cards": None, "players": None,
    }

    xg = _merge(load_xg_map, xg_cache_path, league_id, seasons)
    for pred in iter_xg_predictions(fixtures, xg, target_season=season, k=k):
        if pred["fixture_id"] == _SYNTH_FID:
            card["goals"] = pred["probs"]
            break
    if league_id not in CARDS_LEAGUES or card["goals"] is None:
        return card

    cards_map = _merge(load_cards_map, cards_cache_path, league_id, seasons)
    cards_map[str(_SYNTH_FID)] = {"home_cards": 0, "away_cards": 0}
    for pred in iter_cards_predictions(fixtures, cards_map, score_seasons={season}):
        if pred["fixture_id"] == _SYNTH_FID:
            card["cards"] = {"expected": pred["expected"], "over": pred["over"]}
            break

    players_map = _merge(load_players_map, players_cache_path, league_id, seasons)
    roster = (_expected_roster(players_map, all_fixtures, home_id, as_of_date, _SYNTH_FID)
              + _expected_roster(players_map, all_fixtures, away_id, as_of_date, _SYNTH_FID))
    players_map[str(_SYNTH_FID)] = roster
    for pred in iter_player_predictions(fixtures, players_map, score_seasons={season}):
        if pred["fixture_id"] == _SYNTH_FID:
            card["players"] = sorted(pred["players"], key=lambda x: x["prob"], reverse=True)[:6]
            break
    return card


def predict_round(
    league_id: int, *, season: int, history_seasons: List[int],
    round_name: str, k: float = 5.0,
) -> List[Dict]:
    """
    Predict every match of a given round in one pass (efficient batch).

    Each match is predicted from data before it (point-in-time). Returns a list
    of cards, one per fixture in the round.
    """
    seasons = history_seasons + [season]
    fixtures = load_seasons(league_id, seasons)
    round_fids = {f["fixture_id"] for f in fixtures
                  if f.get("season") == season and f.get("round") == round_name}
    if not round_fids:
        return []

    xg = _merge(load_xg_map, xg_cache_path, league_id, seasons)
    goals = {p["fixture_id"]: p["probs"]
             for p in iter_xg_predictions(fixtures, xg, target_season=season, k=k)
             if p["fixture_id"] in round_fids}

    cards, players = {}, {}
    if league_id in CARDS_LEAGUES:
        cmap = _merge(load_cards_map, cards_cache_path, league_id, seasons)
        for p in iter_cards_predictions(fixtures, cmap, score_seasons={season}):
            if p["fixture_id"] in round_fids:
                cards[p["fixture_id"]] = {"expected": p["expected"], "over": p["over"]}
        pmap = _merge(load_players_map, players_cache_path, league_id, seasons)
        for p in iter_player_predictions(fixtures, pmap, score_seasons={season}):
            if p["fixture_id"] in round_fids:
                players[p["fixture_id"]] = sorted(
                    p["players"], key=lambda x: x["prob"], reverse=True)[:6]

    out = []
    for f in fixtures:
        fid = f["fixture_id"]
        if fid not in round_fids or fid not in goals:
            continue
        out.append({
            "league_id": league_id, "fixture_id": fid,
            "home": f.get("home_name"), "away": f.get("away_name"),
            "date": f.get("date"), "referee": f.get("referee"),
            "goals": goals[fid], "cards": cards.get(fid), "players": players.get(fid),
            "actual": {"home_goals": f.get("home_goals"), "away_goals": f.get("away_goals")},
        })
    return out
