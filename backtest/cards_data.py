"""
Per-match yellow-card data from /fixtures/statistics.

Yellow cards per team per match — the labels and rate inputs for the team cards
model. One API call per fixture (both teams together), cached per league-season.
"""

import asyncio
import os
from typing import Dict, Optional, Tuple

import httpx

from core.config import get_settings
from backtest.data import DATA_DIR, cache_path, load_fixtures, save_fixtures

_FETCH_INTERVAL = 0.25


def cards_cache_path(league_id: int, season: int) -> str:
    return os.path.join(DATA_DIR, f"cards_league_{league_id}_season_{season}.json")


def _extract_cards(
    stats_response: list, home_id: int, away_id: int
) -> Tuple[Optional[int], Optional[int]]:
    """Pull (home_yellows, away_yellows) from a /fixtures/statistics response."""
    yellows: Dict[int, Optional[int]] = {}
    for entry in stats_response or []:
        tid = entry.get("team", {}).get("id")
        val = None
        for st in entry.get("statistics", []):
            if st.get("type") == "Yellow Cards":
                raw = st.get("value")
                val = int(raw) if raw not in (None, "") else 0
                break
        yellows[tid] = val
    return yellows.get(home_id), yellows.get(away_id)


async def fetch_cards_map(league_id: int, season: int) -> Dict[str, Dict]:
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
                f"{base}/fixtures/statistics", headers=headers, params={"fixture": fid},
            )
            hc, ac = _extract_cards(resp.json().get("response", []), fx["home_id"], fx["away_id"])
            if hc is None or ac is None:
                missing += 1
            result[str(fid)] = {"home_cards": hc, "away_cards": ac}
            if i % 50 == 0:
                print(f"  ...{i}/{len(finished)} (senza dati: {missing})")
            await asyncio.sleep(_FETCH_INTERVAL)

    print(f"✅ Cartellini per {len(result)} partite ({missing} senza dati).")
    return result


def load_cards_map(path: str) -> Dict[str, Dict]:
    import json
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


async def get_cards_map(league_id: int, season: int, *, refresh: bool = False) -> Dict[str, Dict]:
    path = cards_cache_path(league_id, season)
    if not refresh and os.path.exists(path):
        return load_cards_map(path)
    cards = await fetch_cards_map(league_id, season)
    save_fixtures(path, cards)   # reuse the JSON writer
    return cards
