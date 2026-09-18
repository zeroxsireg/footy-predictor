"""API di dominio della cache (roster, stats, shots/corners...): stessa interfaccia di RedisFootballCache.

Il host deve fornire `_get_with_decompression(key)`, `_set_with_ttl(key, data, ttl_type, compress)`
e `delete_data(key)`, `_keys_like(pattern)`.
"""

import re
from datetime import datetime
from typing import Dict, List, Optional


def _meta(data_type: str, **extra) -> Dict:
    return {"cached_at": datetime.now().isoformat(), "data_type": data_type, **extra}


class FootballCacheMixin:

    def get_team_roster(self, team_id: int, season: int) -> Optional[List[Dict]]:
        return self._get_with_decompression(f"team:{team_id}:{season}:roster")

    def set_team_roster(self, team_id: int, season: int, roster_data: List[Dict],
                        ttl_type: str = "roster") -> bool:
        return self._set_with_ttl(f"team:{team_id}:{season}:roster", roster_data, ttl_type, compress=True)

    def get_team_shots_corners(self, team_id: int, season: int) -> Optional[Dict]:
        return self._get_with_decompression(f"team:{team_id}:{season}:shots_corners")

    def set_team_shots_corners(self, team_id: int, season: int, stats: Dict) -> bool:
        data = {**stats, "_metadata": _meta("historical_shots_corners", season=season, team_id=team_id)}
        return self._set_with_ttl(f"team:{team_id}:{season}:shots_corners", data, "shots_corners", compress=False)

    def get_team_stats(self, team_id: int, league_id: int, season: int) -> Optional[Dict]:
        return self._get_with_decompression(f"team:{team_id}:{league_id}:{season}:stats")

    def set_team_stats(self, team_id: int, league_id: int, season: int, stats: Dict) -> bool:
        data = {**stats, "_metadata": _meta("historical_team_stats", season=season,
                                            league_id=league_id, team_id=team_id)}
        return self._set_with_ttl(f"team:{team_id}:{league_id}:{season}:stats", data, "team_stats", compress=True)

    def get_match_stats(self, match_id: int) -> Optional[Dict]:
        return self._get_with_decompression(f"match:{match_id}:stats")

    def set_match_stats(self, match_id: int, stats: Dict) -> bool:
        return self._set_with_ttl(f"match:{match_id}:stats", stats, "finished_matches", compress=True)

    def get_cached_teams(self, season: int) -> List[str]:
        """Id (stringa) delle squadre con roster in cache per la stagione."""
        pattern = re.compile(rf"^team:(\d+):{int(season)}:roster$")
        found = (pattern.match(k) for k in self._keys_like(f"team:%:{int(season)}:roster"))
        return [m.group(1) for m in found if m]

    def clear_team_cache(self, team_id: int, season: int = None):
        """Elimina tutte le chiavi di una squadra (una stagione o tutte)."""
        if season:
            patterns = [f"team:{team_id}:{season}:%", f"team:{team_id}:%:{season}:%"]
        else:
            patterns = [f"team:{team_id}:%"]
        for pattern in patterns:
            for key in self._keys_like(pattern):
                self.delete_data(key)

    def is_historical_data(self, data: Dict) -> bool:
        if not data or not isinstance(data, dict):
            return False
        return data.get("_metadata", {}).get("data_type", "") in {
            "historical_team_stats", "historical_shots_corners",
            "historical_match_data", "finished_match_stats",
        }
