"""market_data: public facade of the data layer (fixtures, quotes, results, lineups).

Every function is async and NEVER raises for network/API failures: it logs a short
warning and returns a neutral value ([], {}, None). Quotes come from one bookmaker
per market (rule 11); API pacing is done by the shared HTTP client (>=1s between
calls, sequential, hence below the 5-per-batch limit of rule 10).
"""

import json
from typing import Dict, List, Optional

from backtest import data as season_data
from backtest import xg_data
from core import market_fixtures, market_prices
from core.config import get_settings
from core.contracts import FixtureRef, FixtureResult, PriceQuote
from core.market_http import api_get, log

__all__ = ["get_upcoming_fixtures", "get_prices", "get_benchmark_prices", "get_result",
           "get_lineups", "get_probable_xi", "refresh_current_season_data"]


def _season(season: Optional[int]) -> int:
    return season or get_settings().default_season


async def get_upcoming_fixtures(league_id: int = 135, season: Optional[int] = None,
                                days: int = 3) -> List[FixtureRef]:
    try:
        return await market_fixtures.upcoming_fixtures(league_id, _season(season), days)
    except Exception as exc:
        log.warning("get_upcoming_fixtures failed: %s", exc)
        return []


async def get_prices(fixture_id: int) -> Dict[str, PriceQuote]:
    try:
        books = await market_prices.fetch_bookmakers(fixture_id)
        return market_prices.select_quotes(fixture_id, books) if books else {}
    except Exception as exc:
        log.warning("get_prices %s failed: %s", fixture_id, exc)
        return {}


async def get_benchmark_prices(fixture_id: int) -> Dict[str, PriceQuote]:
    try:
        books = await market_prices.fetch_bookmakers(fixture_id)
        return market_prices.select_benchmark(fixture_id, books) if books else {}
    except Exception as exc:
        log.warning("get_benchmark_prices %s failed: %s", fixture_id, exc)
        return {}


async def get_result(fixture_id: int) -> Optional[FixtureResult]:
    try:
        return await market_fixtures.result(fixture_id)
    except Exception as exc:
        log.warning("get_result %s failed: %s", fixture_id, exc)
        return None


async def get_lineups(fixture_id: int) -> Optional[Dict[int, List[Dict]]]:
    try:
        return await market_fixtures.lineups(fixture_id)
    except Exception as exc:
        log.warning("get_lineups %s failed: %s", fixture_id, exc)
        return None


async def get_probable_xi(team_id: int, season: int, n: int = 3) -> List[Dict]:
    try:
        return await market_fixtures.probable_xi(team_id, season, n)
    except Exception as exc:
        log.warning("get_probable_xi %s failed: %s", team_id, exc)
        return []


async def refresh_current_season_data(league_id: int = 135, season: Optional[int] = None) -> Dict:
    """Refresh fixtures + incremental xG of the CURRENT season only (the two files written).

    Historical seasons are refused (no writes). Existing xG entries are never rewritten;
    an empty/failed fixtures download never overwrites the local file.
    """
    season = _season(season)
    summary = {"fixtures": 0, "xg_added": 0, "api_calls": 0}
    if season != get_settings().default_season:
        log.warning("refresh refused: season %s is not the current one", season)
        return {**summary, "error": "historical season: no writes"}
    try:
        fixtures = await season_data.fetch_season_fixtures(league_id, season)
        summary["api_calls"] += 1
        if not fixtures:
            log.warning("refresh: empty fixtures download, local file kept")
            return summary
        season_data.save_fixtures(season_data.cache_path(league_id, season), fixtures)
        summary["fixtures"] = len(fixtures)

        xg_path = xg_data.xg_cache_path(league_id, season)
        try:
            xg_map = xg_data.load_xg_map(xg_path)
        except (OSError, json.JSONDecodeError):
            xg_map = {}
        added = 0
        try:
            for fx in (f for f in fixtures if f.get("status") == "FT" and str(f["fixture_id"]) not in xg_map):
                stats = await api_get("/fixtures/statistics", {"fixture": fx["fixture_id"]})
                summary["api_calls"] += 1
                if stats is None:
                    continue  # transient failure: retried at the next refresh
                home, away = xg_data._extract_xg(stats, fx["home_id"], fx["away_id"])
                xg_map[str(fx["fixture_id"])] = {"home_xg": home, "away_xg": away}
                added += 1
        finally:
            if added:  # keep what was paid for even if the loop is interrupted
                xg_data.save_xg_map(xg_path, xg_map)
        summary["xg_added"] = added
    except Exception as exc:
        log.warning("refresh_current_season_data failed: %s", exc)
    return summary
