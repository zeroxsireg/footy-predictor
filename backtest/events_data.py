"""
Per-match card data from /fixtures/events.

Unlike /fixtures/statistics (which only covers some leagues), the events endpoint
works everywhere and gives each booking's PLAYER — so one fetch serves both the
team cards model (counts per team) and the player-level model (who got booked).

We count yellow-card events ("ammoniti"): "Yellow Card" and "Second Yellow card".
Straight red cards are excluded (different, rare event).
"""

import asyncio
import os
from typing import Dict, List, Tuple

import httpx

from core.config import get_settings
from backtest.data import DATA_DIR, cache_path, load_fixtures, save_fixtures

_FETCH_INTERVAL = 0.25


def events_cache_path(league_id: int, season: int) -> str:
    return os.path.join(DATA_DIR, f"events_league_{league_id}_season_{season}.json")


def _is_yellow(detail: str) -> bool:
    return "Yellow" in (detail or "")


def extract_card_events(
    events_response: list, home_id: int, away_id: int
) -> Tuple[int, int, List[Dict]]:
    """Return (home_yellows, away_yellows, booked_players) from an events payload."""
    home = away = 0
    players: List[Dict] = []
    for e in events_response or []:
        if e.get("type") != "Card" or not _is_yellow(e.get("detail", "")):
            continue
        team = e.get("team", {}) or {}
        tid = team.get("id")
        if tid == home_id:
            home += 1
        elif tid == away_id:
            away += 1
        pl = e.get("player", {}) or {}
        players.append({
            "player_id": pl.get("id"), "player_name": pl.get("name"),
            "team_id": tid, "detail": e.get("detail"),
            "minute": (e.get("time", {}) or {}).get("elapsed"),
        })
    return home, away, players


async def fetch_events_map(league_id: int, season: int) -> Dict[str, Dict]:
    fixtures = load_fixtures(cache_path(league_id, season))
    finished = [f for f in fixtures if f.get("status") == "FT"]

    settings = get_settings()
    base = settings.api_football_base.rstrip("/")
    headers = {"x-apisports-key": settings.api_football_key}

    result: Dict[str, Dict] = {}
    empty = 0
    async with httpx.AsyncClient(timeout=30) as client:
        for i, fx in enumerate(finished, 1):
            fid = fx["fixture_id"]
            resp = await client.get(
                f"{base}/fixtures/events", headers=headers, params={"fixture": fid},
            )
            data = resp.json().get("response", [])
            hc, ac, players = extract_card_events(data, fx["home_id"], fx["away_id"])
            if hc + ac == 0 and not data:
                empty += 1
            result[str(fid)] = {"home_cards": hc, "away_cards": ac, "players": players}
            if i % 50 == 0:
                print(f"  ...{i}/{len(finished)} (payload vuoti: {empty})")
            await asyncio.sleep(_FETCH_INTERVAL)

    print(f"✅ Eventi per {len(result)} partite ({empty} payload vuoti).")
    return result


def load_events_map(path: str) -> Dict[str, Dict]:
    import json
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


async def get_events_map(league_id: int, season: int, *, refresh: bool = False) -> Dict[str, Dict]:
    path = events_cache_path(league_id, season)
    if not refresh and os.path.exists(path):
        return load_events_map(path)
    events = await fetch_events_map(league_id, season)
    save_fixtures(path, events)
    return events
