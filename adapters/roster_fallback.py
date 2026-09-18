"""Roster lookup that works with Redis off.

Order: in-process cache -> cache persistente (SQLite/Redis) -> API-Football `/players?team=&season=`.

Verified payload (Inter, season 2026, 2 pages of 20): every player carries one
`statistics` entry PER COMPETITION (e.g. Champions League id 2 + Serie A id 135),
so we sum only the domestic-league entries of the requested team. Available
season fields: games.{appearences,minutes,position,lineups,rating}, cards.{yellow,
yellowred,red}, fouls.{committed,drawn}, tackles.{total,blocks,interceptions},
duels.{total,won}. There is NO distance-run / running field in `/players`
(nor in `/fixtures/players`, checked on fixture 1550120).
"""

import time
from typing import Any, Dict, List, Optional, Tuple

from config.leagues import get_league_manager

MEMORY_TTL_SECONDS = 24 * 3600
EMPTY_TTL_SECONDS = 300      # do not hammer the API after a failure
MAX_PAGES = 5                # /players returns 20 players per page

_MEMORY: Dict[Tuple[int, int], Tuple[float, List[Dict]]] = {}


def clear_roster_memory() -> None:
    """Drop the in-process roster cache (used by tests)."""
    _MEMORY.clear()


def _domestic_league_ids() -> set:
    try:
        return {lg.api_league_id for lg in get_league_manager().get_all_leagues() if not lg.is_cup}
    except Exception:
        return set()


def _num(value: Any) -> int:
    return int(value) if isinstance(value, (int, float)) else 0


def _nested(stat: Dict, section: str, field: str) -> int:
    return _num((stat.get(section) or {}).get(field))


def player_from_api(entry: Dict, team_id: int, domestic_ids: set) -> Optional[Dict]:
    """Convert one `/players` response item to the roster dict the analyzers use."""
    info = entry.get("player") or {}
    stats = [s for s in (entry.get("statistics") or []) if (s.get("team") or {}).get("id") == team_id]
    if not info.get("id") or not stats:
        return None
    domestic = [s for s in stats if (s.get("league") or {}).get("id") in domestic_ids]
    chosen = domestic or stats

    position = next((s["games"]["position"] for s in chosen if (s.get("games") or {}).get("position")), None)
    return {
        "id": info.get("id"), "name": info.get("name"),
        "firstname": info.get("firstname"), "lastname": info.get("lastname"),
        "age": info.get("age"), "nationality": info.get("nationality"),
        "position": position,
        "appearances": sum(_nested(s, "games", "appearences") for s in chosen),
        "lineups": sum(_nested(s, "games", "lineups") for s in chosen),
        "minutes": sum(_nested(s, "games", "minutes") for s in chosen),
        "yellow_cards": sum(_nested(s, "cards", "yellow") for s in chosen),
        "red_cards": sum(_nested(s, "cards", "red") for s in chosen),
        "fouls_committed": sum(_nested(s, "fouls", "committed") for s in chosen),
        "fouls_drawn": sum(_nested(s, "fouls", "drawn") for s in chosen),
        "tackles_total": sum(_nested(s, "tackles", "total") for s in chosen),
        "duels_total": sum(_nested(s, "duels", "total") for s in chosen),
        "team_id": team_id,
        "source": "api_fallback",
    }


async def _fetch_from_api(http, team_id: int, season: int) -> List[Dict]:
    domestic_ids = _domestic_league_ids()
    players: List[Dict] = []
    page = 1
    while page <= MAX_PAGES:
        data = await http.request("/players", {"team": team_id, "season": season, "page": page})
        for entry in data.get("response") or []:
            player = player_from_api(entry, team_id, domestic_ids)
            if player:
                players.append(player)
        paging = data.get("paging") or {}
        if page >= _num(paging.get("total")) or not data.get("response"):
            break
        page += 1
    return players


def _persist(cache, team_id: int, season: int, roster: List[Dict]) -> None:
    """Salva il roster API sulla cache persistente con TTL 24h (le statistiche stagionali cambiano)."""
    if cache is None:
        return
    try:
        cache.set_team_roster(team_id, season, roster, ttl_type="league_players_all")
    except TypeError:
        pass  # backend senza parametro ttl_type (Redis storico): nessuna scrittura
    except Exception as exc:
        print(f"⚠️ Persistenza roster non riuscita (team {team_id}): {exc}")


async def get_team_roster_with_fallback(api_client, team_id: int, season: int) -> List[Dict]:
    """Roster of a team as a list of dicts; never raises (empty list + log on failure)."""
    key = (team_id, season)
    cached = _MEMORY.get(key)
    if cached and time.time() < cached[0]:
        return cached[1]

    try:
        redis_cache = getattr(api_client, "redis_cache", None)
        roster = redis_cache.get_team_roster(team_id, season) if redis_cache is not None else None
    except Exception as exc:
        print(f"⚠️ Redis roster non disponibile (team {team_id}): {exc}")
        roster = None
    if roster:
        _MEMORY[key] = (time.time() + MEMORY_TTL_SECONDS, roster)
        return roster

    try:
        http = getattr(api_client, "_http", None)
        if http is None:
            print(f"⚠️ Nessun client HTTP per il fallback roster (team {team_id})")
            roster = []
        else:
            roster = await _fetch_from_api(http, team_id, season)
    except Exception as exc:
        print(f"⚠️ Fallback roster API fallito (team {team_id}, season {season}): {exc}")
        roster = []

    if roster:
        _persist(getattr(api_client, "redis_cache", None), team_id, season, roster)
    ttl = MEMORY_TTL_SECONDS if roster else EMPTY_TTL_SECONDS
    _MEMORY[key] = (time.time() + ttl, roster)
    return roster
