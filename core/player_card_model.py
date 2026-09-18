"""
Player booking probability model: P(player receives a yellow | he plays).

Pure probability estimator (rule 6): no odds, no stake logic. It is the single
source of truth shared by the point-in-time backtest (backtest/player_cards.py)
and the live analyzer (analyzers/player_cards_analyzer.py).

Parameter provenance: k=64 and the goalkeeper exclusion were chosen on
Serie A 2024 (history 2023) and confirmed unchanged on La Liga 2024
(Brier skill -0.008/-0.004 -> +0.015/+0.019 on outfield players).

Signals:
  * the player's own booking rate, shrunk toward the POSITION rate
    (which is itself shrunk toward the league rate);
  * the referee's strictness (shrunk toward the league average);
  * the player's foul rate relative to the league (when coverage allows);
  * an online recalibration keeping mean predicted bookings aligned with reality.
"""

from dataclasses import dataclass
from typing import Dict, Optional

P_CLAMP = (0.01, 0.9)
REF_CLAMP = (0.6, 1.6)
FOULS_CLAMP = (0.6, 1.6)
RECAL_CLAMP = (0.7, 1.3)

# Fallbacks used before any league history is available (cold start / live).
DEFAULT_LEAGUE_RATE = 0.15
DEFAULT_LEAGUE_CARDS_PER_MATCH = 4.0


@dataclass(frozen=True)
class CardModelParams:
    k: float = 64.0           # player shrinkage strength (pseudo-appearances)
    ref_k: float = 8.0        # referee shrinkage (pseudo-matches)
    pos_k: float = 20.0       # position shrinkage toward league rate
    fouls_k: float = 5.0      # fouls shrinkage
    min_apps: int = 3
    min_fouls_apps: int = 3
    excluded_positions: tuple = ("G",)   # keepers: ~3-6% base rate, no signal


DEFAULT_PARAMS = CardModelParams()


def clamp(x: float, lo: float, hi: float) -> float:
    return min(hi, max(lo, x))


def booked_flag(player: Dict) -> int:
    return 1 if (player.get("yellow") or 0) >= 1 else 0


def ref_name(raw) -> str:
    return str(raw).split(",")[0].strip() if raw else ""


@dataclass
class PlayerStat:
    apps: int = 0
    yellows: int = 0
    fouls_sum: float = 0.0
    fouls_apps: int = 0     # appearances with foul data (coverage ~50%)

    def update(self, booked: int, fouls=None) -> None:
        self.apps += 1
        self.yellows += booked
        if fouls is not None:
            self.fouls_sum += fouls
            self.fouls_apps += 1


@dataclass
class RefStat:
    matches: int = 0
    cards: int = 0

    def update(self, total_cards: int) -> None:
        self.matches += 1
        self.cards += total_cards


def position_rate(pos_stat: Optional[PlayerStat], league_rate: float,
                  params: CardModelParams = DEFAULT_PARAMS) -> float:
    """Position booking rate shrunk toward the league rate."""
    if pos_stat is None:
        return league_rate
    return (pos_stat.yellows + params.pos_k * league_rate) / (pos_stat.apps + params.pos_k)


def player_rate(stat: PlayerStat, pos_base: float,
                params: CardModelParams = DEFAULT_PARAMS) -> float:
    """Own booking rate shrunk toward the position prior (few apps -> prior)."""
    return (stat.yellows + params.k * pos_base) / (stat.apps + params.k)


def referee_factor(ref: Optional[RefStat], league_cards_avg: float,
                   params: CardModelParams = DEFAULT_PARAMS) -> float:
    if ref is None or ref.matches <= 0 or league_cards_avg <= 0:
        return 1.0
    rate = (ref.cards + params.ref_k * league_cards_avg) / (ref.matches + params.ref_k)
    return clamp(rate / league_cards_avg, *REF_CLAMP)


def fouls_factor(stat: PlayerStat, league_fouls_avg: float,
                 params: CardModelParams = DEFAULT_PARAMS) -> float:
    if stat.fouls_apps < params.min_fouls_apps or league_fouls_avg <= 0:
        return 1.0
    fr = (stat.fouls_sum + params.fouls_k * league_fouls_avg) / (stat.fouls_apps + params.fouls_k)
    return clamp(fr / league_fouls_avg, *FOULS_CLAMP)


def raw_probability(stat: PlayerStat, pos_base: float, ref_factor: float,
                    foul_factor: float, params: CardModelParams = DEFAULT_PARAMS) -> float:
    """Uncalibrated probability (also the quantity fed to the recalibrator)."""
    return player_rate(stat, pos_base, params) * ref_factor * foul_factor


def final_probability(raw: float, recal: float = 1.0) -> float:
    return clamp(raw * recal, *P_CLAMP)


class PlayerCardModel:
    """
    Stateful point-in-time model. Usage per match: predict_match(...) for the
    players on the pitch, THEN update_match(...) with the realised roster.
    """

    def __init__(self, params: CardModelParams = DEFAULT_PARAMS):
        self.params = params
        self.players: Dict[int, PlayerStat] = {}
        self.positions: Dict[str, PlayerStat] = {}
        self.refs: Dict[str, RefStat] = {}
        self.lg_yellows = self.lg_apps = 0
        self.lg_cards = self.lg_matches = 0
        self.lg_fouls_sum = 0.0
        self.lg_fouls_apps = 0
        self.recal_pred = self.recal_act = 0.0

    def league_rate(self) -> float:
        return self.lg_yellows / self.lg_apps if self.lg_apps else DEFAULT_LEAGUE_RATE

    def league_cards_avg(self) -> float:
        return self.lg_cards / self.lg_matches if self.lg_matches else DEFAULT_LEAGUE_CARDS_PER_MATCH

    def league_fouls_avg(self) -> float:
        return self.lg_fouls_sum / self.lg_fouls_apps if self.lg_fouls_apps else 0.0

    def recalibration(self) -> float:
        if self.recal_pred <= 0:
            return 1.0
        return clamp(self.recal_act / self.recal_pred, *RECAL_CLAMP)

    def predict_match(self, played, referee: str = "") -> list:
        """Rows (dict with prob) for each player with enough history."""
        p = self.params
        base = self.league_rate()
        ref_f = referee_factor(self.refs.get(referee), self.league_cards_avg(), p) if referee else 1.0
        recal = self.recalibration()
        fouls_avg = self.league_fouls_avg()
        rows = []
        for pl in played:
            pid = pl.get("player_id")
            ps = self.players.get(pid)
            if pid is None or ps is None or ps.apps < p.min_apps:
                continue
            pos = pl.get("position") or "?"
            if pos in p.excluded_positions:
                continue
            pos_base = position_rate(self.positions.get(pos), base, p)
            raw = raw_probability(ps, pos_base, ref_f, fouls_factor(ps, fouls_avg, p), p)
            booked = booked_flag(pl)
            rows.append({"player_id": pid, "name": pl.get("name"),
                         "team_id": pl.get("team_id"), "position": pos,
                         "prob": final_probability(raw, recal), "booked": booked})
            self.recal_pred += raw
            self.recal_act += booked
        return rows

    def update_match(self, played, referee: str = "") -> None:
        total_cards = sum(booked_flag(pl) for pl in played)
        for pl in played:
            pid = pl.get("player_id")
            booked = booked_flag(pl)
            pos = pl.get("position") or "?"
            fouls = pl.get("fouls")
            if pid is not None:
                self.players.setdefault(pid, PlayerStat()).update(booked, fouls)
            self.positions.setdefault(pos, PlayerStat()).update(booked)
            self.lg_yellows += booked
            self.lg_apps += 1
            if fouls is not None:
                self.lg_fouls_sum += fouls
                self.lg_fouls_apps += 1
        if referee:
            self.refs.setdefault(referee, RefStat()).update(total_cards)
        self.lg_cards += total_cards
        self.lg_matches += 1


# ── Live estimation (no league history: static priors measured on the cached
#    Serie A + La Liga 2023-24 lineups, ~47k appearances) ─────────────────────
LIVE_POSITION_PRIORS = {"D": 0.167, "M": 0.149, "F": 0.099}
LIVE_FOULS_PER_APP = 1.6

_POSITION_ALIASES = {
    "defender": "D", "centre-back": "D", "left-back": "D", "right-back": "D",
    "wing-back": "D", "midfielder": "M", "attacker": "F", "forward": "F",
    "goalkeeper": "G", "d": "D", "m": "M", "f": "F", "g": "G",
}


def normalize_position(raw) -> str:
    """Map API position strings ('Defender', 'D', ...) to G/D/M/F ('?' if unknown)."""
    if not isinstance(raw, str):
        return "?"
    return _POSITION_ALIASES.get(raw.strip().lower(), "?")


def live_probability(appearances: int, yellows: int, position: str,
                     fouls: Optional[float] = None,
                     params: CardModelParams = DEFAULT_PARAMS) -> Optional[float]:
    """
    P(booked) for one player from season totals. Few appearances -> the
    position prior dominates. None when the player is out of scope (keeper,
    unknown position, never played).
    """
    pos = normalize_position(position)
    if pos in params.excluded_positions or pos not in LIVE_POSITION_PRIORS:
        return None
    if not appearances or appearances <= 0:
        return None
    stat = PlayerStat(apps=int(appearances), yellows=int(yellows or 0))
    if fouls is not None:
        stat.fouls_sum, stat.fouls_apps = float(fouls), int(appearances)
    foul_f = fouls_factor(stat, LIVE_FOULS_PER_APP, params)
    raw = raw_probability(stat, LIVE_POSITION_PRIORS[pos], 1.0, foul_f, params)
    return final_probability(raw)
