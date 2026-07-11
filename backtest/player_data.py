"""
Per-match player data from /fixtures/players.

For each fixture, the lineup with per-player minutes, position, yellow cards and
fouls. This single endpoint gives the player-level model everything it needs:
the population (who played), the features (position, accumulated card/foul
rates) and the labels (booked this match or not).
"""

import asyncio
import os
from typing import Dict, List

import httpx

from core.config import get_settings
from backtest.data import DATA_DIR, cache_path, load_fixtures, save_fixtures

_FETCH_INTERVAL = 0.25


def players_cache_path(league_id: int, season: int) -> str:
    return os.path.join(DATA_DIR, f"players_league_{league_id}_season_{season}.json")


def extract_players(response: list) -> List[Dict]:
    """Flatten a /fixtures/players payload into per-player records."""
    out: List[Dict] = []
    for team in response or []:
        tid = (team.get("team") or {}).get("id")
        for p in team.get("players", []):
            stats = (p.get("statistics") or [{}])[0] or {}
            games = stats.get("games") or {}
            cards = stats.get("cards") or {}
            fouls = stats.get("fouls") or {}
            out.append({
                "player_id": (p.get("player") or {}).get("id"),
                "name": (p.get("player") or {}).get("name"),
                "team_id": tid,
                "minutes": games.get("minutes"),
                "position": games.get("position"),
                "yellow": cards.get("yellow") or 0,
                "fouls": fouls.get("committed"),
            })
    return out


async def fetch_players_map(league_id: int, season: int) -> Dict[str, List[Dict]]:
    fixtures = load_fixtures(cache_path(league_id, season))
    finished = [f for f in fixtures if f.get("status") == "FT"]

    settings = get_settings()
    base = settings.api_football_base.rstrip("/")
    headers = {"x-apisports-key": settings.api_football_key}

    result: Dict[str, List[Dict]] = {}
    empty = 0
    async with httpx.AsyncClient(timeout=30) as client:
        for i, fx in enumerate(finished, 1):
            fid = fx["fixture_id"]
            resp = await client.get(
                f"{base}/fixtures/players", headers=headers, params={"fixture": fid},
            )
            players = extract_players(resp.json().get("response", []))
            if not players:
                empty += 1
            result[str(fid)] = players
            if i % 50 == 0:
                print(f"  ...{i}/{len(finished)} (vuoti: {empty})")
            await asyncio.sleep(_FETCH_INTERVAL)

    print(f"✅ Formazioni per {len(result)} partite ({empty} vuote).")
    return result


def load_players_map(path: str) -> Dict[str, List[Dict]]:
    import json
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


async def get_players_map(league_id: int, season: int, *, refresh: bool = False) -> Dict[str, List[Dict]]:
    path = players_cache_path(league_id, season)
    if not refresh and os.path.exists(path):
        return load_players_map(path)
    players = await fetch_players_map(league_id, season)
    save_fixtures(path, players)
    return players
