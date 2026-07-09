"""
Expected Goals (xG) data: fetch per-fixture xG from /fixtures/statistics and
cache it, keyed by fixture id.

xG is the research's #1 lever: it stabilises the variance that raw goal counts
suffer from. One API call per fixture (both teams come back together), cached so
we fetch each season only once.
"""

import asyncio
import json
import os
from typing import Dict, Optional, Tuple

import httpx

from core.config import get_settings
from backtest.data import DATA_DIR, cache_path, load_fixtures

_FETCH_INTERVAL = 0.25   # seconds between calls (Pro plan tolerates this easily)


def xg_cache_path(league_id: int, season: int) -> str:
    return os.path.join(DATA_DIR, f"xg_league_{league_id}_season_{season}.json")


def _extract_xg(
    stats_response: list, home_id: int, away_id: int
) -> Tuple[Optional[float], Optional[float]]:
    """
    Pull (home_xg, away_xg) from a /fixtures/statistics response.

    The response is a list with one entry per team; each carries a list of
    typed statistics including 'expected_goals' (a string like "1.30" or None).
    Returns (None, None) when xG is absent (older/uncovered matches).
    """
    xg_by_team: Dict[int, Optional[float]] = {}
    for entry in stats_response or []:
        tid = entry.get("team", {}).get("id")
        value = None
        for st in entry.get("statistics", []):
            if st.get("type") == "expected_goals":
                raw = st.get("value")
                value = float(raw) if raw not in (None, "") else None
                break
        xg_by_team[tid] = value
    return xg_by_team.get(home_id), xg_by_team.get(away_id)


async def fetch_xg_map(league_id: int, season: int) -> Dict[str, Dict]:
    """
    Fetch xG for every finished fixture of a league-season.

    Returns {str(fixture_id): {"home_xg": x, "away_xg": y}}. Requires the season
    fixtures to be cached already (run_backtest.py fetches them).
    """
    fixtures = load_fixtures(cache_path(league_id, season))
    finished = [f for f in fixtures if f.get("status") == "FT"]

    settings = get_settings()
    base = settings.api_football_base.rstrip("/")
    headers = {"x-apisports-key": settings.api_football_key}

    result: Dict[str, Dict] = {}
    missing = 0
    async with httpx.AsyncClient(timeout=30) as client:
        for i, fx in enumerate(finished, 1):
            fid = fx["fixture_id"]
            resp = await client.get(
                f"{base}/fixtures/statistics", headers=headers,
                params={"fixture": fid},
            )
            data = resp.json()
            home_xg, away_xg = _extract_xg(
                data.get("response", []), fx["home_id"], fx["away_id"]
            )
            if home_xg is None or away_xg is None:
                missing += 1
            result[str(fid)] = {"home_xg": home_xg, "away_xg": away_xg}
            if i % 50 == 0:
                print(f"  ...{i}/{len(finished)} partite (xG mancanti finora: {missing})")
            await asyncio.sleep(_FETCH_INTERVAL)

    print(f"✅ xG recuperati per {len(result)} partite ({missing} senza xG).")
    return result


def save_xg_map(path: str, xg_map: Dict[str, Dict]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(xg_map, fh, ensure_ascii=False, indent=2)


def load_xg_map(path: str) -> Dict[str, Dict]:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


async def get_xg_map(league_id: int, season: int, *, refresh: bool = False) -> Dict[str, Dict]:
    """Cache-first xG map for a league-season."""
    path = xg_cache_path(league_id, season)
    if not refresh and os.path.exists(path):
        return load_xg_map(path)
    xg_map = await fetch_xg_map(league_id, season)
    save_xg_map(path, xg_map)
    return xg_map
