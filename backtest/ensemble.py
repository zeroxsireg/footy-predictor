"""
Ensemble evaluation: Poisson-strength vs Glicko-2 vs their average, on 1X2.

One chronological point-in-time pass maintains BOTH model states (weighted
Poisson accumulators + Glicko ratings) so all three are scored on the exact
same target-season matches — a fair three-way comparison.
"""

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List

from backtest.advanced import (
    WeightedTeam, WeightedLeague, AdvContext, predict as poisson_predict,
    _to_days,
)
from backtest import glicko
from backtest.metrics import score_multiclass, MulticlassMarketResult


@dataclass
class EnsembleResult:
    label: str
    scored: MulticlassMarketResult


def _rows_to_1x2(preds: Dict[str, float]) -> Dict[str, float]:
    return {"1": preds["result_1"], "X": preds["result_X"], "2": preds["result_2"]}


def _blend(a: Dict[str, float], b: Dict[str, float]) -> Dict[str, float]:
    return {k: (a[k] + b[k]) / 2.0 for k in ("1", "X", "2")}


def run_ensemble_eval(
    fixtures: List[Dict],
    target_season: int,
    *,
    xi: float = 0.002,
    k: float = 5.0,
    use_mov: bool = True,
) -> List[EnsembleResult]:
    """Score Poisson, Glicko-2 and the ensemble on the target season's 1X2."""
    ordered = sorted(fixtures, key=lambda r: (r["date"], r["fixture_id"]))
    if not ordered:
        return []
    epoch = datetime.fromisoformat(ordered[0]["date"].replace("Z", "+00:00"))

    teams: Dict[int, WeightedTeam] = {}
    league = WeightedLeague()
    ratings: Dict[int, glicko.GlickoRating] = {}
    lg_matches = 0
    lg_goals = 0

    def wteam(tid): return teams.setdefault(tid, WeightedTeam())
    def rating(tid): return ratings.setdefault(tid, glicko.GlickoRating())

    rows = {"Poisson forze": [], "Glicko-2": [], "Ensemble": []}

    for rec in ordered:
        if rec.get("status") != "FT":
            continue
        hg, ag = rec.get("home_goals"), rec.get("away_goals")
        if hg is None or ag is None:
            continue
        hid, aid = rec["home_id"], rec["away_id"]
        home_w, away_w = wteam(hid), wteam(aid)
        home_r, away_r = rating(hid), rating(aid)

        if rec.get("season") == target_season:
            ctx = AdvContext(
                season=target_season, date=rec["date"],
                home_name=rec["home_name"], away_name=rec["away_name"],
                home_w=home_w.w, home_gf_w=home_w.gf_w, home_ga_w=home_w.ga_w,
                away_w=away_w.w, away_gf_w=away_w.gf_w, away_ga_w=away_w.ga_w,
                lg_overall_avg=league.overall_avg(),
                lg_home_avg=league.home_avg(), lg_away_avg=league.away_avg(),
                home_goals=hg, away_goals=ag,
            )
            total = lg_goals / lg_matches if lg_matches > 0 else glicko.DEFAULT_TOTAL
            p_pois = _rows_to_1x2(poisson_predict(ctx, k=k))
            p_glk = _rows_to_1x2(glicko.predict_1x2(home_r, away_r, total_goals=total))
            actual = ctx.result
            rows["Poisson forze"].append((p_pois, actual))
            rows["Glicko-2"].append((p_glk, actual))
            rows["Ensemble"].append((_blend(p_pois, p_glk), actual))

        # ── updates (after prediction) ──
        weight = math.exp(xi * _to_days(rec["date"], epoch))
        home_w.update(weight, hg, ag)
        away_w.update(weight, ag, hg)
        league.update(weight, hg, ag)

        mov = glicko.mov_multiplier(hg - ag) if use_mov else 1.0
        score = 1.0 if hg > ag else 0.5 if hg == ag else 0.0
        new_home = glicko.updated(home_r, away_r, score, mov=mov, rating_bonus=glicko.HOME_ADV)
        new_away = glicko.updated(away_r, home_r, 1.0 - score, mov=mov, rating_bonus=-glicko.HOME_ADV)
        ratings[hid], ratings[aid] = new_home, new_away

        lg_matches += 1
        lg_goals += hg + ag

    return [EnsembleResult(name, score_multiclass(name, r)) for name, r in rows.items()]
