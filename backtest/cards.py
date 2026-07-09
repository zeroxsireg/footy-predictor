"""
Team/match yellow-cards model.

Expected total cards from: each team's card-propensity (cards received per
match, relative to the league) and the REFEREE's strictness (their cards per
match, relative to the league). Both are recency-weighted and Bayesian-shrunk
toward the league mean — thin samples (few games, new referees) pull to average.

Point-in-time as always: predict from pre-match rates, then update.
"""

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Tuple

from analyzers.base import BaseAnalyzer
from backtest.advanced import _to_days
from backtest.metrics import BinaryMarketResult, score_binary

_PROP_CLAMP = (0.5, 1.8)
LINES = (3.5, 4.5, 5.5)


@dataclass
class Counter:
    """Recency-weighted running mean of a quantity (cards)."""
    w: float = 0.0
    x_w: float = 0.0

    def update(self, weight: float, x: float) -> None:
        self.w += weight
        self.x_w += weight * x


def _clamp(x: float) -> float:
    lo, hi = _PROP_CLAMP
    return min(hi, max(lo, x))


def _shrunk(x_w: float, w: float, prior: float, k: float) -> float:
    if (w + k) <= 0:
        return prior
    return (x_w + k * prior) / (w + k)


def _ref_name(raw) -> str:
    if not raw:
        return ""
    return str(raw).split(",")[0].strip()   # drop country suffix if present


@dataclass
class CardsReport:
    n: int
    ref_coverage: float          # share of scored matches with a known referee
    mae: float                   # mean abs error of expected vs actual total cards
    avg_expected: float
    avg_actual: float
    lines: List[BinaryMarketResult] = field(default_factory=list)


def run_cards_backtest(
    fixtures: List[Dict], cards_map: Dict[str, Dict], *,
    xi: float = 0.0, k: float = 6.0, ref_k: float = 8.0, min_matches: int = 4,
    score_seasons: set | None = None,
) -> CardsReport:
    ordered = sorted(fixtures, key=lambda r: (r["date"], r["fixture_id"]))
    ordered = [r for r in ordered if r.get("status") == "FT"]
    if not ordered:
        return CardsReport(0, 0.0, 0.0, 0.0, 0.0)
    epoch = datetime.fromisoformat(ordered[0]["date"].replace("Z", "+00:00"))

    teams: Dict[int, Counter] = {}
    refs: Dict[str, Counter] = {}
    league_cards_w = league_w = 0.0
    count: Dict[int, int] = {}

    def tc(t): return teams.setdefault(t, Counter())
    def rc(r): return refs.setdefault(r, Counter())

    pairs = {ln: [] for ln in LINES}
    abs_err: List[float] = []
    exp_list: List[float] = []
    act_list: List[float] = []
    ref_known = 0
    scored = 0

    for rec in ordered:
        fid = str(rec["fixture_id"])
        cm = cards_map.get(fid)
        if not cm or cm.get("home_cards") is None or cm.get("away_cards") is None:
            continue
        hid, aid = rec["home_id"], rec["away_id"]
        home_cards, away_cards = cm["home_cards"], cm["away_cards"]
        total = home_cards + away_cards
        th, ta = tc(hid), tc(aid)
        ref = _ref_name(rec.get("referee"))

        in_scope = score_seasons is None or rec.get("season") in score_seasons
        if in_scope and count.get(hid, 0) >= min_matches and count.get(aid, 0) >= min_matches:
            base_total = (league_cards_w / league_w) if league_w > 0 else 4.0
            team_base = base_total / 2.0
            prop_h = _clamp(_shrunk(th.x_w, th.w, team_base, k) / team_base)
            prop_a = _clamp(_shrunk(ta.x_w, ta.w, team_base, k) / team_base)
            if ref and refs.get(ref) and refs[ref].w > 0:
                ref_rate = _shrunk(refs[ref].x_w, refs[ref].w, base_total, ref_k)
                ref_factor = _clamp(ref_rate / base_total)
                ref_known += 1
            else:
                ref_factor = 1.0
            lam = max(0.5, base_total * (prop_h + prop_a) / 2.0 * ref_factor)

            scored += 1
            for ln in LINES:
                p_over = BaseAnalyzer._poisson_over_prob(lam, ln)
                pairs[ln].append((p_over, 1 if total > ln else 0))
            abs_err.append(abs(lam - total))
            exp_list.append(lam)
            act_list.append(total)

        # ── updates ──
        weight = math.exp(xi * _to_days(rec["date"], epoch))
        th.update(weight, home_cards)
        ta.update(weight, away_cards)
        if ref:
            rc(ref).update(weight, total)
        league_cards_w += weight * total
        league_w += weight
        count[hid] = count.get(hid, 0) + 1
        count[aid] = count.get(aid, 0) + 1

    return CardsReport(
        n=scored,
        ref_coverage=round(ref_known / scored, 3) if scored else 0.0,
        mae=round(sum(abs_err) / len(abs_err), 3) if abs_err else 0.0,
        avg_expected=round(sum(exp_list) / len(exp_list), 2) if exp_list else 0.0,
        avg_actual=round(sum(act_list) / len(act_list), 2) if act_list else 0.0,
        lines=[score_binary(f"Over {ln} cartellini", pairs[ln]) for ln in LINES],
    )
