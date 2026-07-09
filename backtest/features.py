"""
Point-in-time feature extraction for the gradient-boosting model.

Turns every match into a numeric feature vector built ONLY from information
available before kick-off: the xG-parametric model's own probabilities, xG
attack/defence strengths, Glicko ratings, recent form and goal rates. The GBM
then learns to combine these signals — a step up from the single parametric
Poisson.

Same golden rule as the rest of backtest/: snapshot + emit, then update.
"""

import math
from datetime import datetime
from typing import Dict, List

import pandas as pd

from core.models import Team, TeamStats  # noqa: F401 (kept for parity)
from backtest.advanced import (
    WeightedTeam, WeightedLeague, AdvContext, expected_goals, predict as strength_predict,
    _to_days,
)
from backtest import glicko

# Numeric columns the model trains on.
FEATURE_COLS = [
    "xg_lam_home", "xg_lam_away", "xg_lam_total", "xg_lam_diff",
    "pois_over15", "pois_over25", "pois_over35", "pois_btts",
    "pois_p1", "pois_pX", "pois_p2",
    "g_lam_home", "g_lam_away",
    "glk_diff", "glk_home_rd", "glk_away_rd", "glk_p1", "glk_pX", "glk_p2",
    "home_form", "away_form", "form_diff",
    "home_gpg", "away_gpg", "home_gapg", "away_gapg",
    "home_matches", "away_matches", "lg_avg_total",
]


def _ctx(home: WeightedTeam, away: WeightedTeam, league: WeightedLeague) -> AdvContext:
    return AdvContext(
        season=0, date="", home_name="", away_name="",
        home_w=home.w, home_gf_w=home.gf_w, home_ga_w=home.ga_w,
        away_w=away.w, away_gf_w=away.gf_w, away_ga_w=away.ga_w,
        lg_overall_avg=league.overall_avg(),
        lg_home_avg=league.home_avg(), lg_away_avg=league.away_avg(),
        home_goals=0, away_goals=0,
    )


def _form_points(results: List[str]) -> int:
    return sum(3 if r == "W" else 1 if r == "D" else 0 for r in results[-5:])


def iter_feature_rows(
    fixtures: List[Dict], xg_map: Dict[str, Dict], *,
    xi: float = 0.0, k: float = 5.0, min_matches: int = 4,
):
    """Yield one feature+label row per scored match (point-in-time)."""
    ordered = sorted(fixtures, key=lambda r: (r["date"], r["fixture_id"]))
    ordered = [r for r in ordered if r.get("status") == "FT"
               and r.get("home_goals") is not None and r.get("away_goals") is not None]
    if not ordered:
        return
    epoch = datetime.fromisoformat(ordered[0]["date"].replace("Z", "+00:00"))

    xg_t: Dict[int, WeightedTeam] = {}
    g_t: Dict[int, WeightedTeam] = {}
    xg_lg, g_lg = WeightedLeague(), WeightedLeague()
    ratings: Dict[int, glicko.GlickoRating] = {}
    form: Dict[int, List[str]] = {}
    count: Dict[int, int] = {}
    lg_goals = lg_matches = 0

    def xt(t): return xg_t.setdefault(t, WeightedTeam())
    def gt(t): return g_t.setdefault(t, WeightedTeam())
    def rt(t): return ratings.setdefault(t, glicko.GlickoRating())
    def ft(t): return form.setdefault(t, [])

    for rec in ordered:
        hid, aid = rec["home_id"], rec["away_id"]
        hg, ag = rec["home_goals"], rec["away_goals"]
        xh, xa, gh, ga = xt(hid), xt(aid), gt(hid), gt(aid)
        rh, ra = rt(hid), rt(aid)

        if count.get(hid, 0) >= min_matches and count.get(aid, 0) >= min_matches:
            xctx = _ctx(xh, xa, xg_lg)
            gctx = _ctx(gh, ga, g_lg)
            xlh, xla = expected_goals(xctx, k=k)
            glh, gla = expected_goals(gctx, k=k)
            pois = strength_predict(xctx, k=k)
            lg_avg_total = (lg_goals / lg_matches) if lg_matches else glicko.DEFAULT_TOTAL
            glk = glicko.predict_1x2(rh, ra, total_goals=lg_avg_total)
            hf, af = _form_points(ft(hid)), _form_points(ft(aid))

            total = hg + ag
            yield {
                "season": rec.get("season", 0), "fixture_id": rec["fixture_id"],
                # features
                "xg_lam_home": xlh, "xg_lam_away": xla,
                "xg_lam_total": xlh + xla, "xg_lam_diff": xlh - xla,
                "pois_over15": pois["over_1_5"], "pois_over25": pois["over_2_5"],
                "pois_over35": pois["over_3_5"], "pois_btts": pois["btts_yes"],
                "pois_p1": pois["result_1"], "pois_pX": pois["result_X"], "pois_p2": pois["result_2"],
                "g_lam_home": glh, "g_lam_away": gla,
                "glk_diff": (rh.r + glicko.HOME_ADV) - ra.r,
                "glk_home_rd": rh.rd, "glk_away_rd": ra.rd,
                "glk_p1": glk["result_1"], "glk_pX": glk["result_X"], "glk_p2": glk["result_2"],
                "home_form": hf, "away_form": af, "form_diff": hf - af,
                "home_gpg": gh.gf_w / gh.w if gh.w else 0.0,
                "away_gpg": ga.gf_w / ga.w if ga.w else 0.0,
                "home_gapg": gh.ga_w / gh.w if gh.w else 0.0,
                "away_gapg": ga.ga_w / ga.w if ga.w else 0.0,
                "home_matches": count.get(hid, 0), "away_matches": count.get(aid, 0),
                "lg_avg_total": lg_avg_total,
                # labels
                "y_over25": 1 if total > 2.5 else 0,
                "y_btts": 1 if hg > 0 and ag > 0 else 0,
                "y_result": "1" if hg > ag else "2" if hg < ag else "X",
            }

        # ── updates ──
        w = math.exp(xi * _to_days(rec["date"], epoch))
        xg = xg_map.get(str(rec["fixture_id"]), {})
        hx, ax_ = xg.get("home_xg"), xg.get("away_xg")
        if hx is None or ax_ is None:
            hx, ax_ = float(hg), float(ag)
        xh.update(w, hx, ax_); xa.update(w, ax_, hx); xg_lg.update(w, hx, ax_)
        gh.update(w, hg, ag); ga.update(w, ag, hg); g_lg.update(w, hg, ag)

        mov = glicko.mov_multiplier(hg - ag)
        s = 1.0 if hg > ag else 0.5 if hg == ag else 0.0
        ratings[hid] = glicko.updated(rh, ra, s, mov=mov, rating_bonus=glicko.HOME_ADV)
        ratings[aid] = glicko.updated(ra, rh, 1.0 - s, mov=mov, rating_bonus=-glicko.HOME_ADV)
        ft(hid).append("W" if hg > ag else "D" if hg == ag else "L")
        ft(aid).append("W" if ag > hg else "D" if hg == ag else "L")
        count[hid] = count.get(hid, 0) + 1
        count[aid] = count.get(aid, 0) + 1
        lg_goals += hg + ag
        lg_matches += 1


def build_feature_frame(
    fixtures: List[Dict], xg_map: Dict[str, Dict], **kwargs
) -> pd.DataFrame:
    """Materialise all feature rows into a DataFrame."""
    return pd.DataFrame(list(iter_feature_rows(fixtures, xg_map, **kwargs)))
