"""
Yellow-card candidates of a fixture (probability only: the API offers no quotes).

Ranking of candidates, NOT a certainty: expected discrimination is modest
(AUC ~0.61 in point-in-time backtests on Serie A / La Liga) and probabilities are
calibrated by bucket, not per player.

p_booked = P(booked | plays) * P(plays):
  * P(booked | plays): shared model (core/player_card_model.live_probability):
    position prior, own rate shrunk (k=64), fouls per appearance, referee strictness;
    goalkeepers are excluded.
  * P(plays): official lineup (1.0 / 0.0) when available, otherwise the probable XI
    (start_share / minutes_share); a squad player missing from the probable XI keeps a
    small non-zero probability derived from his historical share of minutes.
Players no longer in `squads` are never included.
"""

from typing import Dict, List, Optional

from core.contracts import FixtureRef, PlayerCandidate
from core.player_card_model import live_probability, normalize_position

ABSENT_START_CAP = 0.10     # max start_prob of a squad player missing from the probable XI
ABSENT_START_FLOOR = 0.02


def _share(entry: Dict) -> Optional[float]:
    for key in ("start_share", "minutes_share"):
        if entry.get(key) is not None:
            return float(entry[key])
    return None


def _historical_share(player: Dict, max_minutes: float) -> float:
    return (player.get("minutes") or 0) / max_minutes if max_minutes > 0 else 0.0


def _start_prob(player: Dict, team_id: int, probable_xi: Dict[int, List[Dict]],
                official: Dict[int, List[Dict]], max_minutes: float):
    """(start_prob, source label) for one squad player."""
    pid = player.get("id")
    if official.get(team_id):
        starts = any(p.get("id") == pid for p in official[team_id])
        return (1.0 if starts else 0.0), "formazione ufficiale"
    entry = next((p for p in probable_xi.get(team_id) or [] if p.get("id") == pid), None)
    if entry is not None and _share(entry) is not None:
        return min(1.0, max(ABSENT_START_FLOOR, _share(entry))), "probabile XI"
    hist = _historical_share(player, max_minutes)
    prob = min(ABSENT_START_CAP, max(ABSENT_START_FLOOR, 0.25 * hist))
    return prob, "fuori dal probabile XI"


def _note(player: Dict, start: float, source: str, ref_factor: float) -> str:
    apps = player.get("appearances") or 0
    parts = [f"{player.get('yellow_cards') or 0} gialli in {apps} pres."]
    fouls = player.get("fouls_committed") or 0
    if fouls and apps:
        parts.append(f"{fouls / apps:.1f} falli/pres.")
    parts.append(f"{source}: gioca {start:.0%}")
    if abs(ref_factor - 1.0) >= 0.005:
        parts.append(f"arbitro x{ref_factor:.2f}")
    return ", ".join(parts)


def rank_booking_candidates(
    fixture: FixtureRef,
    squads: Dict[int, List[Dict]],
    probable_xi: Dict[int, List[Dict]],
    referee_strictness: float = 1.0,
    official_lineups: Optional[Dict[int, List[Dict]]] = None,
    top_n: int = 8,
) -> List[PlayerCandidate]:
    """Top-N players most likely to be booked, sorted by p_booked (desc)."""
    official = official_lineups or {}
    teams = {fixture.home_id: fixture.home, fixture.away_id: fixture.away}
    out: List[PlayerCandidate] = []
    for team_id, team_name in teams.items():
        roster = squads.get(team_id) or []
        max_minutes = max((p.get("minutes") or 0 for p in roster), default=0)
        for player in roster:
            if player.get("id") is None:
                continue
            p_given = live_probability(
                player.get("appearances") or 0, player.get("yellow_cards") or 0,
                player.get("position"), fouls=player.get("fouls_committed") or None,
                ref_factor=referee_strictness)
            if p_given is None:
                continue
            start, source = _start_prob(player, team_id, probable_xi, official, max_minutes)
            if start <= 0.0:
                continue
            out.append(PlayerCandidate(
                fixture_id=fixture.fixture_id, player_id=player["id"],
                name=player.get("name") or "?", team=team_name,
                position=normalize_position(player.get("position")),
                p_booked_given_plays=p_given, start_prob=start, p_booked=p_given * start,
                note=_note(player, start, source, referee_strictness)))
    out.sort(key=lambda c: (-c.p_booked, c.player_id))
    return out[:top_n]
