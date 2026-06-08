"""Team statistics service — fetches, parses and caches team data."""

from typing import Any, Dict, Optional

from core.models import Team, TeamStats
from adapters.http_client import FootballHTTPClient, FootballAPIError


class TeamStatsService:
    """
    Responsible for everything related to team season statistics.

    Knows how to: fetch season stats, aggregate shots/corners from
    individual match records, parse raw API responses, and populate
    the Redis cache.  Nothing else.
    """

    def __init__(self, http: FootballHTTPClient, cache):
        self._http = http
        self._cache = cache

    # ── public ────────────────────────────────────────────────────────────────

    async def get_team_statistics(
        self, team_id: int, league_id: int, season: int
    ) -> TeamStats:
        """Return season stats for a team, using Redis cache when available."""
        cached = self._cache.get_team_stats(team_id, league_id, season)
        if cached:
            print(f"📊 Using cached team stats for team {team_id}")
            return self._hydrate_team_stats(cached)

        print(f"🔄 Fetching fresh team stats for team {team_id} from API...")
        params = {"team": team_id, "league": league_id, "season": season}
        data = await self._http.request("/teams/statistics", params)

        if not data.get("response") and season >= 2024:
            params["season"] = season - 1
            data = await self._http.request("/teams/statistics", params)

        if not data.get("response"):
            raise FootballAPIError(
                f"No statistics found for team {team_id} in seasons {season}/{season-1}"
            )

        team_stats = self._parse_team_statistics(data["response"])

        shots_corners = await self._get_team_shots_corners(team_id, league_id, season)
        team_stats.shots_total = shots_corners["shots_total"]
        team_stats.shots_on_target = shots_corners["shots_on_target"]
        team_stats.corners = shots_corners["corners"]

        self._cache.set_team_stats(team_id, league_id, season, self._to_cache_dict(team_stats))
        print(f"✅ Cached team stats for team {team_id}")
        return team_stats

    async def force_update(
        self, team_id: int, league_id: int, season: int
    ) -> Optional[TeamStats]:
        """Bypass cache and re-fetch fresh statistics."""
        print(f"🔄 Force updating team statistics for team {team_id}...")
        self._cache.delete_data(f"team_stats:{team_id}:{league_id}:{season}")
        try:
            stats = await self.get_team_statistics(team_id, league_id, season)
            print(f"✅ Force updated team statistics for team {team_id}")
            return stats
        except Exception as exc:
            print(f"❌ Failed to update team statistics for team {team_id}: {exc}")
            return None

    # ── internal ──────────────────────────────────────────────────────────────

    async def _get_team_shots_corners(
        self, team_id: int, league_id: int, season: int
    ) -> Dict[str, int]:
        cached = self._cache.get_team_shots_corners(team_id, season)
        if cached and cached.get("matches_processed", 0) > 0:
            print(f"📊 Using cached shots/corners for team {team_id}")
            return {k: cached[k] for k in ("shots_total", "shots_on_target", "corners")}

        print(f"🔄 Calculating shots/corners for team {team_id} from all season matches...")
        params = {"team": team_id, "league": league_id, "season": season}

        try:
            data = await self._http.request("/fixtures", params)
            if not data.get("response"):
                empty = {"shots_total": 0, "shots_on_target": 0, "corners": 0}
                self._cache.set_team_shots_corners(team_id, season, {**empty, "matches_processed": 0})
                return empty

            existing = cached or {}
            processed = set(existing.get("processed_matches", []))
            shots = existing.get("shots_total", 0)
            shots_ot = existing.get("shots_on_target", 0)
            corners = existing.get("corners", 0)
            count = existing.get("matches_processed", 0)
            new_matches = 0

            for fixture in data["response"]:
                if fixture["fixture"]["status"]["short"] != "FT":
                    continue
                match_id = fixture["fixture"]["id"]
                if match_id in processed:
                    continue

                new_matches += 1
                match_data = await self._get_match_statistics(match_id, team_id)
                if match_data:
                    shots += match_data["shots"]
                    shots_ot += match_data["shots_on_target"]
                    corners += match_data["corners"]
                    processed.add(match_id)
                    count += 1

            result = {
                "shots_total": shots,
                "shots_on_target": shots_ot,
                "corners": corners,
                "matches_processed": count,
                "processed_matches": list(processed),
            }
            self._cache.set_team_shots_corners(team_id, season, result)
            if new_matches > 0:
                print(f"✅ Processed {new_matches} new matches for team {team_id}")

            return {k: result[k] for k in ("shots_total", "shots_on_target", "corners")}

        except Exception as exc:
            print(f"⚠️ Could not fetch shots/corners for team {team_id}: {exc}")
            return {"shots_total": 0, "shots_on_target": 0, "corners": 0}

    async def _get_match_statistics(
        self, match_id: int, team_id: int
    ) -> Optional[Dict[str, int]]:
        try:
            data = await self._http.request("/fixtures/statistics", {"fixture": match_id})
            if not data.get("response"):
                return None
            for team_stats in data["response"]:
                if team_stats["team"]["id"] == team_id:
                    s = {stat["type"]: stat["value"] for stat in team_stats["statistics"]}
                    return {
                        "shots": int(s.get("Total Shots", 0) or 0),
                        "shots_on_target": int(s.get("Shots on Goal", 0) or 0),
                        "corners": int(s.get("Corner Kicks", 0) or 0),
                    }
        except Exception as exc:
            print(f"⚠️ Could not fetch match statistics for match {match_id}: {exc}")
        return None

    # ── parsers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _parse_team_statistics(stats_data: Dict[str, Any]) -> TeamStats:
        team_info = stats_data["team"]
        fixtures = stats_data["fixtures"]
        goals = stats_data["goals"]

        def safe(data, *keys, default=0):
            try:
                r = data
                for k in keys:
                    r = r[k]
                return r if r is not None else default
            except (KeyError, TypeError):
                return default

        yellow_total = sum(
            d["total"]
            for d in stats_data.get("cards", {}).get("yellow", {}).values()
            if d and d.get("total")
        )
        red_total = sum(
            d["total"]
            for d in stats_data.get("cards", {}).get("red", {}).values()
            if d and d.get("total")
        )

        def score_margin(s):
            try:
                a, b = s.split("-")
                return abs(int(a) - int(b))
            except Exception:
                return 0

        biggest_win = max(
            score_margin(safe(stats_data, "biggest", "wins", "home", default="0-0")),
            score_margin(safe(stats_data, "biggest", "wins", "away", default="0-0")),
        )
        biggest_loss = max(
            score_margin(safe(stats_data, "biggest", "loses", "home", default="0-0")),
            score_margin(safe(stats_data, "biggest", "loses", "away", default="0-0")),
        )

        return TeamStats(
            team=Team(id=team_info["id"], name=team_info["name"], logo=team_info["logo"]),
            matches_played=safe(fixtures, "played", "total"),
            wins=safe(fixtures, "wins", "total"),
            draws=safe(fixtures, "draws", "total"),
            losses=safe(fixtures, "loses", "total"),
            goals_for=safe(goals, "for", "total", "total"),
            goals_against=safe(goals, "against", "total", "total"),
            shots_total=0,
            shots_on_target=0,
            corners=0,
            yellow_cards=yellow_total,
            red_cards=red_total,
            form=safe(stats_data, "form", default=""),
            clean_sheets=safe(stats_data, "clean_sheet", "total"),
            failed_to_score=safe(stats_data, "failed_to_score", "total"),
            penalties_scored=safe(stats_data, "penalty", "scored", "total"),
            penalties_missed=safe(stats_data, "penalty", "missed", "total"),
            biggest_win_margin=biggest_win,
            biggest_loss_margin=biggest_loss,
            over_1_5_goals=safe(stats_data, "goals", "for", "under_over", "1.5", "over"),
            over_2_5_goals=safe(stats_data, "goals", "for", "under_over", "2.5", "over"),
            over_3_5_goals=safe(stats_data, "goals", "for", "under_over", "3.5", "over"),
            over_1_5_conceded=safe(stats_data, "goals", "against", "under_over", "1.5", "over"),
            over_2_5_conceded=safe(stats_data, "goals", "against", "under_over", "2.5", "over"),
            over_3_5_conceded=safe(stats_data, "goals", "against", "under_over", "3.5", "over"),
        )

    @staticmethod
    def _hydrate_team_stats(d: Dict[str, Any]) -> TeamStats:
        """Reconstruct TeamStats from a Redis-cached dict."""
        team = Team(id=d["team"]["id"], name=d["team"]["name"], logo=d["team"]["logo"])
        return TeamStats(
            team=team,
            matches_played=d["matches_played"],
            wins=d["wins"],
            draws=d["draws"],
            losses=d["losses"],
            goals_for=d["goals_for"],
            goals_against=d["goals_against"],
            shots_total=d["shots_total"],
            shots_on_target=d["shots_on_target"],
            corners=d["corners"],
            yellow_cards=d["yellow_cards"],
            red_cards=d["red_cards"],
            form=d.get("form", ""),
            clean_sheets=d.get("clean_sheets", 0),
            failed_to_score=d.get("failed_to_score", 0),
            penalties_scored=d.get("penalties_scored", 0),
            penalties_missed=d.get("penalties_missed", 0),
            biggest_win_margin=d.get("biggest_win_margin", 0),
            biggest_loss_margin=d.get("biggest_loss_margin", 0),
            over_1_5_goals=d.get("over_1_5_goals", 0),
            over_2_5_goals=d.get("over_2_5_goals", 0),
            over_3_5_goals=d.get("over_3_5_goals", 0),
            over_1_5_conceded=d.get("over_1_5_conceded", 0),
            over_2_5_conceded=d.get("over_2_5_conceded", 0),
            over_3_5_conceded=d.get("over_3_5_conceded", 0),
        )

    @staticmethod
    def _to_cache_dict(ts: TeamStats) -> Dict[str, Any]:
        return {
            "team": {"id": ts.team.id, "name": ts.team.name, "logo": ts.team.logo},
            "matches_played": ts.matches_played,
            "wins": ts.wins,
            "draws": ts.draws,
            "losses": ts.losses,
            "goals_for": ts.goals_for,
            "goals_against": ts.goals_against,
            "shots_total": ts.shots_total,
            "shots_on_target": ts.shots_on_target,
            "corners": ts.corners,
            "yellow_cards": ts.yellow_cards,
            "red_cards": ts.red_cards,
            "form": ts.form,
            "clean_sheets": ts.clean_sheets,
            "failed_to_score": ts.failed_to_score,
            "penalties_scored": ts.penalties_scored,
            "penalties_missed": ts.penalties_missed,
            "biggest_win_margin": ts.biggest_win_margin,
            "biggest_loss_margin": ts.biggest_loss_margin,
            "over_1_5_goals": ts.over_1_5_goals,
            "over_2_5_goals": ts.over_2_5_goals,
            "over_3_5_goals": ts.over_3_5_goals,
            "over_1_5_conceded": ts.over_1_5_conceded,
            "over_2_5_conceded": ts.over_2_5_conceded,
            "over_3_5_conceded": ts.over_3_5_conceded,
        }
