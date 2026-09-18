"""Fixtures, results, lineups and probable XI (payloads verified on Serie A 2026).

/fixtures/players: per team `players[].statistics[0].games` has `minutes` (None if
unused), `substitute` (False = starter) and `position`; `cards.yellow` is the yellow
count (agrees with /fixtures/events on the verified match). /fixtures/lineups:
`startXI` / `substitutes` lists of {player:{id,name,pos}}.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from core.contracts import FixtureRef, FixtureResult
from core.market_http import api_get, cached, log


def _parse_fixture(item: Dict[str, Any], league_id: int, season: int) -> Optional[FixtureRef]:
    try:
        fx, teams = item["fixture"], item["teams"]
        kickoff = datetime.fromisoformat(fx["date"])
        if kickoff.tzinfo is None:
            kickoff = kickoff.replace(tzinfo=timezone.utc)
        return FixtureRef(
            fixture_id=fx["id"], kickoff=kickoff.astimezone(timezone.utc),
            home=teams["home"]["name"], away=teams["away"]["name"],
            home_id=teams["home"]["id"], away_id=teams["away"]["id"],
            league_id=league_id, season=season,
            round=item.get("league", {}).get("round", "") or "",
            referee=fx.get("referee") or None, status=fx["status"]["short"])
    except (KeyError, TypeError, ValueError):
        return None


async def upcoming_fixtures(league_id: int, season: int, days: int) -> List[FixtureRef]:
    today = datetime.now(timezone.utc).date()
    response = await api_get("/fixtures", {
        "league": league_id, "season": season, "status": "NS",
        "from": today.isoformat(), "to": (today + timedelta(days=days)).isoformat()})
    parsed = [_parse_fixture(i, league_id, season) for i in response or []]
    return sorted((f for f in parsed if f and f.status == "NS"), key=lambda f: (f.kickoff, f.fixture_id))


async def fixture_players(fixture_id: int) -> Optional[List[Dict[str, Any]]]:
    """Flat per-player stats of a FINISHED fixture (immutable -> cached forever)."""
    async def load():
        response = await api_get("/fixtures/players", {"fixture": fixture_id})
        if not response:
            return None
        rows = []
        for team in response:
            for entry in team.get("players", []):
                stats = (entry.get("statistics") or [{}])[0]
                games = stats.get("games") or {}
                rows.append({
                    "team_id": team["team"]["id"], "id": entry["player"]["id"],
                    "name": entry["player"].get("name", ""), "position": games.get("position") or "",
                    "minutes": games.get("minutes") or 0, "starter": games.get("substitute") is False,
                    "yellow": (stats.get("cards") or {}).get("yellow") or 0})
        return rows
    return await cached(f"mkt:players:{fixture_id}", "finished_matches", load)


async def result(fixture_id: int) -> Optional[FixtureResult]:
    response = await api_get("/fixtures", {"id": fixture_id})
    if not response:
        return None
    item = response[0]
    status, goals = item["fixture"]["status"]["short"], item.get("goals") or {}
    booked: List[int] = []
    if status == "FT":
        rows = await fixture_players(fixture_id)
        if rows is None:  # never settle player picks on a failed lookup: let the caller retry
            log.warning("result %s: players unavailable, result withheld", fixture_id)
            return None
        booked = sorted({r["id"] for r in rows if r["yellow"] > 0})
    return FixtureResult(fixture_id=fixture_id, status=status, home_goals=goals.get("home"),
                         away_goals=goals.get("away"), booked_player_ids=booked)


async def lineups(fixture_id: int) -> Optional[Dict[int, List[Dict]]]:
    response = await api_get("/fixtures/lineups", {"fixture": fixture_id})
    if not response:
        return None
    out: Dict[int, List[Dict]] = {}
    for team in response:
        players = [{"id": p["player"]["id"], "name": p["player"].get("name", ""),
                    "position": p["player"].get("pos") or "", "starter": starter}
                   for key, starter in (("startXI", True), ("substitutes", False))
                   for p in team.get(key, [])]
        out[team["team"]["id"]] = players
    return out or None


async def probable_xi(team_id: int, season: int, n: int) -> List[Dict]:
    """Starters estimate from the team's last `n` FINISHED games (denominator = games found)."""
    async def load():
        return await api_get("/fixtures", {"team": team_id, "season": season, "last": n})
    last = await cached(f"mkt:last:{team_id}:{season}:{n}", "live_odds", load, max_age=600)
    ids = [i["fixture"]["id"] for i in last or [] if i["fixture"]["status"]["short"] == "FT"][-n:]
    stats: Dict[int, Dict[str, Any]] = {}
    games = 0
    for fid in ids:
        rows = await fixture_players(fid)
        if rows is None:
            continue
        games += 1
        for r in (r for r in rows if r["team_id"] == team_id):
            s = stats.setdefault(r["id"], {"id": r["id"], "name": r["name"], "position": r["position"],
                                           "starts": 0, "minutes": 0})
            s["starts"] += 1 if r["starter"] else 0
            s["minutes"] += r["minutes"]
    if games == 0:
        return []
    out = [{"id": s["id"], "name": s["name"], "position": s["position"],
            "start_share": s["starts"] / games, "minutes_share": s["minutes"] / (90 * games)}
           for s in stats.values()]
    return sorted(out, key=lambda p: (-p["start_share"], -p["minutes_share"], p["id"]))
