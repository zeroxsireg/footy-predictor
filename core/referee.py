"""
Referee strictness index (point-in-time, offline).

strictness = referee's cards/match relative to the league average, shrunk toward
1.0 and clamped to [0.6, 1.6]. The maths is the shared one of
core/player_card_model.py (RefStat + referee_factor, SSOT); this module only
feeds it from the cached fixtures (referee, date) and cards files (cards per match).

Offline validation (Serie A 2024, history 2023): player-booking AUC +0.010
(0.598 -> 0.608); La Liga 2024: +0.002 (same sign, weaker).
"""

import glob
import json
import os
import re
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from backtest.data import DATA_DIR
from core.player_card_model import RefStat, ref_name, referee_factor

DEFAULT_LEAGUE_ID = 135  # Serie A only (lean pipeline)


def _parse(iso: str) -> datetime:
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _load_json(path: str):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _cards_matches(data_dir: str, league_id: int) -> List[Tuple[datetime, str, int]]:
    """(date, referee, total cards) of every cached match with referee and cards data."""
    rows: List[Tuple[datetime, str, int]] = []
    pattern = os.path.join(data_dir, f"cards_league_{league_id}_season_*.json")
    for cards_path in sorted(glob.glob(pattern)):
        season = re.search(r"season_(\d+)\.json$", cards_path).group(1)
        fixtures_path = os.path.join(data_dir, f"league_{league_id}_season_{season}.json")
        if not os.path.exists(fixtures_path):
            continue
        cards = _load_json(cards_path)
        for rec in _load_json(fixtures_path):
            entry = cards.get(str(rec["fixture_id"]))
            ref = ref_name(rec.get("referee"))
            if not entry or not ref or rec.get("status") != "FT":
                continue
            total = (entry.get("home_cards") or 0) + (entry.get("away_cards") or 0)
            rows.append((_parse(rec["date"]), ref, total))
    return rows


def strictness(referee: Optional[str], before_date: Optional[datetime] = None, *,
               league_id: int = DEFAULT_LEAGUE_ID, data_dir: Optional[str] = None) -> float:
    """Referee severity index (1.0 = league average; unknown referee -> 1.0)."""
    name = ref_name(referee)
    if not name:
        return 1.0
    rows = _cards_matches(data_dir or DATA_DIR, league_id)
    if before_date is not None:
        cutoff = before_date if before_date.tzinfo else before_date.replace(tzinfo=timezone.utc)
        rows = [r for r in rows if r[0] < cutoff]
    if not rows:
        return 1.0
    league_avg = sum(r[2] for r in rows) / len(rows)
    stat = RefStat()
    for _, ref, total in rows:
        if ref == name:
            stat.update(total)
    return referee_factor(stat if stat.matches else None, league_avg)
