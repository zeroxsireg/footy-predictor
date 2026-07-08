"""
Advanced 1X2 track — the "free squeeze" recommended by the research.

Techniques implemented (all without paid data / xG):
  - multi-season history concatenated into one continuous timeline
    (no stats reset at season boundaries)
  - exponential time-decay weighting  w_i = exp(xi * t_i)  so recent matches
    count more; xi is a tunable hyper-parameter (optimised by sweep)
  - GLOBAL home advantage (league-wide) instead of noisy per-team home/away
    splits
  - Bayesian shrinkage of each team's attack/defence toward the league mean,
    which protects early-season / low-sample estimates

The point-in-time guarantee is preserved: a match is predicted from the
weighted accumulators, which are updated only AFTER the prediction.

Numerical note: with w_i = exp(xi*t_i) the current-time factor exp(-xi*t0)
cancels in every rate (goals_weighted / weight), so we can keep simple running
sums and never rescale — the absolute weight scale is irrelevant.
"""

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Iterator, List

from backtest.models import _score_matrix, _markets_from_matrix

_STRENGTH_CLAMP = (0.25, 3.0)
_MIN_LAMBDA = 0.15


# ── running state ─────────────────────────────────────────────────────────────

@dataclass
class WeightedTeam:
    """Recency-weighted attack/defence tally for one team (home+away combined)."""
    matches: int = 0        # raw count (for gating / diagnostics)
    w: float = 0.0          # sum of time weights
    gf_w: float = 0.0       # weighted goals for
    ga_w: float = 0.0       # weighted goals against

    def update(self, weight: float, goals_for: int, goals_against: int) -> None:
        self.matches += 1
        self.w += weight
        self.gf_w += weight * goals_for
        self.ga_w += weight * goals_against


@dataclass
class WeightedLeague:
    """Recency-weighted league totals, for baselines and global home advantage."""
    w: float = 0.0          # sum of per-match weights
    home_goals_w: float = 0.0
    away_goals_w: float = 0.0

    def update(self, weight: float, home_goals: int, away_goals: int) -> None:
        self.w += weight
        self.home_goals_w += weight * home_goals
        self.away_goals_w += weight * away_goals

    def home_avg(self) -> float:
        return self.home_goals_w / self.w if self.w > 0 else 1.5

    def away_avg(self) -> float:
        return self.away_goals_w / self.w if self.w > 0 else 1.1

    def overall_avg(self) -> float:
        return (self.home_avg() + self.away_avg()) / 2.0


@dataclass
class AdvContext:
    """Pre-match sufficient statistics handed to the model (no leakage)."""
    season: int
    date: str
    home_name: str
    away_name: str
    # weighted team sufficient stats
    home_w: float
    home_gf_w: float
    home_ga_w: float
    away_w: float
    away_gf_w: float
    away_ga_w: float
    # league baselines (weighted, pre-match)
    lg_overall_avg: float
    lg_home_avg: float
    lg_away_avg: float
    # actual result
    home_goals: int
    away_goals: int

    @property
    def result(self) -> str:
        if self.home_goals > self.away_goals:
            return "1"
        if self.home_goals < self.away_goals:
            return "2"
        return "X"


# ── replay ────────────────────────────────────────────────────────────────────

def _to_days(iso: str, epoch: datetime) -> float:
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return (dt - epoch).total_seconds() / 86400.0


def iter_advanced_contexts(
    fixtures: List[Dict], xi: float, score_seasons: set | None = None
) -> Iterator[AdvContext]:
    """
    Replay a (multi-season) fixture list with time-decay weight exp(xi * days).

    Accumulators build up over ALL matches; a context is yielded only for
    matches whose season is in `score_seasons` (None = score everything).
    Weights and league state are updated after each yield -> point-in-time.
    """
    ordered = sorted(fixtures, key=lambda r: (r["date"], r["fixture_id"]))
    if not ordered:
        return
    epoch = datetime.fromisoformat(ordered[0]["date"].replace("Z", "+00:00"))

    teams: Dict[int, WeightedTeam] = {}
    league = WeightedLeague()

    def team(tid: int) -> WeightedTeam:
        t = teams.get(tid)
        if t is None:
            t = teams[tid] = WeightedTeam()
        return t

    for rec in ordered:
        if rec.get("status") != "FT":
            continue
        hg, ag = rec.get("home_goals"), rec.get("away_goals")
        if hg is None or ag is None:
            continue

        home = team(rec["home_id"])
        away = team(rec["away_id"])

        if score_seasons is None or rec.get("season") in score_seasons:
            yield AdvContext(
                season=rec.get("season", 0),
                date=rec["date"],
                home_name=rec["home_name"],
                away_name=rec["away_name"],
                home_w=home.w, home_gf_w=home.gf_w, home_ga_w=home.ga_w,
                away_w=away.w, away_gf_w=away.gf_w, away_ga_w=away.ga_w,
                lg_overall_avg=league.overall_avg(),
                lg_home_avg=league.home_avg(),
                lg_away_avg=league.away_avg(),
                home_goals=hg, away_goals=ag,
            )

        weight = math.exp(xi * _to_days(rec["date"], epoch))
        home.update(weight, hg, ag)
        away.update(weight, ag, hg)
        league.update(weight, hg, ag)


# ── model ─────────────────────────────────────────────────────────────────────

def _clamp(x: float) -> float:
    lo, hi = _STRENGTH_CLAMP
    return min(hi, max(lo, x))


def _shrunk_strength(goals_w: float, w: float, league_avg: float, k: float) -> float:
    """
    Attack or defence strength, Bayesian-shrunk toward the league mean.

    k = number of pseudo-matches at league average. Thin samples (small w) get
    pulled toward 1.0; well-observed teams keep their signal.
    """
    if league_avg <= 0 or (w + k) <= 0:
        return 1.0   # no information (and no shrinkage) -> league average
    shrunk_rate = (goals_w + k * league_avg) / (w + k)
    return _clamp(shrunk_rate / league_avg)


def expected_goals(ctx: AdvContext, k: float = 5.0):
    """Home/away expected goals from shrunk strengths and global home advantage."""
    overall = max(0.3, ctx.lg_overall_avg)
    hfa_home = ctx.lg_home_avg / overall if overall > 0 else 1.0
    hfa_away = ctx.lg_away_avg / overall if overall > 0 else 1.0

    home_attack = _shrunk_strength(ctx.home_gf_w, ctx.home_w, overall, k)
    home_defence = _shrunk_strength(ctx.home_ga_w, ctx.home_w, overall, k)
    away_attack = _shrunk_strength(ctx.away_gf_w, ctx.away_w, overall, k)
    away_defence = _shrunk_strength(ctx.away_ga_w, ctx.away_w, overall, k)

    lam_home = max(_MIN_LAMBDA, overall * home_attack * away_defence * hfa_home)
    lam_away = max(_MIN_LAMBDA, overall * away_attack * home_defence * hfa_away)
    return lam_home, lam_away


def predict(ctx: AdvContext, k: float = 5.0, rho: float = 0.0) -> Dict[str, float]:
    """Full market probabilities for one match (fractions in [0, 1])."""
    lam_home, lam_away = expected_goals(ctx, k=k)
    return _markets_from_matrix(_score_matrix(lam_home, lam_away, rho=rho))
