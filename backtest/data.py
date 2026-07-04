"""
Season data: fetch once from the API, cache to a local JSON file, reuse offline.

A completed season is a fixed dataset, so we hit the API a single time (one bulk
`/fixtures` call, paginated if needed) and never again — every backtest run
afterwards reads the local cache. This keeps API usage at ~1 request.
"""

import json
import os
from typing import Any, Dict, List, Optional

# Where cached season files live (git-ignored — regenerable data, not source).
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


def cache_path(league_id: int, season: int) -> str:
    return os.path.join(DATA_DIR, f"league_{league_id}_season_{season}.json")


def _normalize_fixture(fd: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Reduce a raw API fixture to the flat record the backtest needs."""
    try:
        fixture = fd["fixture"]
        teams = fd["teams"]
        goals = fd["goals"]
        return {
            "fixture_id": fixture["id"],
            "date": fixture["date"],
            "status": fixture["status"]["short"],
            "round": fd.get("league", {}).get("round", ""),
            "home_id": teams["home"]["id"],
            "home_name": teams["home"]["name"],
            "away_id": teams["away"]["id"],
            "away_name": teams["away"]["name"],
            "home_goals": goals["home"],
            "away_goals": goals["away"],
        }
    except (KeyError, TypeError):
        return None


async def fetch_season_fixtures(league_id: int, season: int) -> List[Dict[str, Any]]:
    """
    Fetch every fixture of a league-season from the API (all pages).

    Imports the HTTP client lazily so that offline backtest runs never touch
    the network stack or require API credentials.
    """
    from adapters.http_client import FootballHTTPClient

    http = FootballHTTPClient()
    records: List[Dict[str, Any]] = []
    page = 1
    while True:
        data = await http.request(
            "/fixtures", {"league": league_id, "season": season, "page": page}
        )
        for fd in data.get("response", []):
            rec = _normalize_fixture(fd)
            if rec:
                records.append(rec)

        paging = data.get("paging", {}) or {}
        total_pages = paging.get("total", 1) or 1
        if page >= total_pages:
            break
        page += 1

    records.sort(key=lambda r: (r["date"], r["fixture_id"]))
    return records


def save_fixtures(path: str, fixtures: List[Dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(fixtures, fh, ensure_ascii=False, indent=2)


def load_fixtures(path: str) -> List[Dict[str, Any]]:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


async def get_season_fixtures(
    league_id: int, season: int, *, refresh: bool = False
) -> List[Dict[str, Any]]:
    """
    Return season fixtures, fetching from the API only if not already cached
    (or when refresh=True). Cache-first: the common case makes zero API calls.
    """
    path = cache_path(league_id, season)
    if not refresh and os.path.exists(path):
        return load_fixtures(path)

    fixtures = await fetch_season_fixtures(league_id, season)
    save_fixtures(path, fixtures)
    return fixtures
