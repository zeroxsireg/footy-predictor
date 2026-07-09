"""
Goals vs xG head-to-head.

One point-in-time pass maintains two parallel sets of weighted accumulators —
one fed by real goals, one fed by xG — and scores both models on the SAME
matches and markets. Identical everything except the input signal, so any
difference is purely the value of xG.

Actual outcomes (over/under, BTTS, 1X2) always come from real goals; only the
model's *inputs* differ.
"""

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List

from backtest.advanced import (
    WeightedTeam, WeightedLeague, AdvContext, predict as strength_predict, _to_days,
)
from backtest.metrics import (
    BinaryMarketResult, MulticlassMarketResult, score_binary, score_multiclass,
)

_BINARY = {
    "Over 1.5 Goals": "over_1_5",
    "Over 2.5 Goals": "over_2_5",
    "Over 3.5 Goals": "over_3_5",
    "BTTS Yes": "btts_yes",
}


@dataclass
class ModelScores:
    label: str
    binary: List[BinaryMarketResult]
    result_1x2: MulticlassMarketResult


@dataclass
class XgComparison:
    n: int
    xg_missing: int
    models: Dict[str, ModelScores]   # "Gol" and "xG"


def _outcome(hg: int, ag: int, key: str) -> int:
    total = hg + ag
    if key == "over_1_5":
        return 1 if total > 1.5 else 0
    if key == "over_2_5":
        return 1 if total > 2.5 else 0
    if key == "over_3_5":
        return 1 if total > 3.5 else 0
    if key == "btts_yes":
        return 1 if hg > 0 and ag > 0 else 0
    raise ValueError(key)


def _result(hg: int, ag: int) -> str:
    return "1" if hg > ag else "2" if hg < ag else "X"


def _ctx(home: WeightedTeam, away: WeightedTeam, league: WeightedLeague,
         hg: int, ag: int) -> AdvContext:
    return AdvContext(
        season=0, date="", home_name="", away_name="",
        home_w=home.w, home_gf_w=home.gf_w, home_ga_w=home.ga_w,
        away_w=away.w, away_gf_w=away.gf_w, away_ga_w=away.ga_w,
        lg_overall_avg=league.overall_avg(),
        lg_home_avg=league.home_avg(), lg_away_avg=league.away_avg(),
        home_goals=hg, away_goals=ag,
    )


def run_xg_comparison(
    fixtures: List[Dict],
    xg_map: Dict[str, Dict],
    *,
    xi: float = 0.0,
    k: float = 5.0,
    min_matches: int = 4,
    score_seasons: set | None = None,
) -> XgComparison:
    """
    Score a goals-fed model and an xG-fed model on the same matches.

    With `score_seasons` set, prior seasons still build history but only the
    listed season(s) are scored — so the models get multi-season memory.
    """
    ordered = sorted(fixtures, key=lambda r: (r["date"], r["fixture_id"]))
    ordered = [r for r in ordered if r.get("status") == "FT"
               and r.get("home_goals") is not None and r.get("away_goals") is not None]
    if not ordered:
        return XgComparison(0, 0, {})
    epoch = datetime.fromisoformat(ordered[0]["date"].replace("Z", "+00:00"))

    g_teams: Dict[int, WeightedTeam] = {}
    x_teams: Dict[int, WeightedTeam] = {}
    g_league, x_league = WeightedLeague(), WeightedLeague()
    g_count: Dict[int, int] = {}

    binary = {"Gol": {m: [] for m in _BINARY}, "xG": {m: [] for m in _BINARY}}
    rows_1x2 = {"Gol": [], "xG": []}
    scored = 0
    xg_missing = 0

    def gt(tid): return g_teams.setdefault(tid, WeightedTeam())
    def xt(tid): return x_teams.setdefault(tid, WeightedTeam())

    for rec in ordered:
        hid, aid = rec["home_id"], rec["away_id"]
        hg, ag = rec["home_goals"], rec["away_goals"]
        gh, ga = gt(hid), gt(aid)
        xh, xa = xt(hid), xt(aid)

        in_scope = score_seasons is None or rec.get("season") in score_seasons
        if in_scope and g_count.get(hid, 0) >= min_matches and g_count.get(aid, 0) >= min_matches:
            scored += 1
            g_ctx = _ctx(gh, ga, g_league, hg, ag)
            x_ctx = _ctx(xh, xa, x_league, hg, ag)
            g_pred = strength_predict(g_ctx, k=k)
            x_pred = strength_predict(x_ctx, k=k)
            for market, key in _BINARY.items():
                out = _outcome(hg, ag, key)
                binary["Gol"][market].append((g_pred[key], out))
                binary["xG"][market].append((x_pred[key], out))
            actual = _result(hg, ag)
            rows_1x2["Gol"].append(({"1": g_pred["result_1"], "X": g_pred["result_X"], "2": g_pred["result_2"]}, actual))
            rows_1x2["xG"].append(({"1": x_pred["result_1"], "X": x_pred["result_X"], "2": x_pred["result_2"]}, actual))

        # ── updates (after prediction) ──
        weight = math.exp(xi * _to_days(rec["date"], epoch))
        gh.update(weight, hg, ag)
        ga.update(weight, ag, hg)
        g_league.update(weight, hg, ag)
        g_count[hid] = g_count.get(hid, 0) + 1
        g_count[aid] = g_count.get(aid, 0) + 1

        xg = xg_map.get(str(rec["fixture_id"]), {})
        home_xg, away_xg = xg.get("home_xg"), xg.get("away_xg")
        if home_xg is None or away_xg is None:
            home_xg, away_xg = float(hg), float(ag)   # fallback to real goals
            xg_missing += 1
        xh.update(weight, home_xg, away_xg)
        xa.update(weight, away_xg, home_xg)
        x_league.update(weight, home_xg, away_xg)

    def scores(name: str) -> ModelScores:
        return ModelScores(
            label=name,
            binary=[score_binary(m, binary[name][m]) for m in _BINARY],
            result_1x2=score_multiclass("1X2", rows_1x2[name]),
        )

    return XgComparison(
        n=scored, xg_missing=xg_missing,
        models={"Gol": scores("Gol"), "xG": scores("xG")},
    )
