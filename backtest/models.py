"""
Prediction models for the backtest comparison.

Three models, all producing the same 7 probabilities per match so they can be
scored head-to-head:

  baseline_model        - the CURRENT app maths (season averages, no defence,
                          no home/away split). Our reference point.
  poisson_strength_model- expected goals from attack strength x opponent defence
                          weakness x home/away league baseline, independent
                          Poisson. Fixes the two flaws the backtest exposed.
  dixon_coles_model     - same expected goals, plus the Dixon-Coles low-score
                          correlation correction (0-0, 1-0, 0-1, 1-1).

The last two share _expected_goals() and _score_matrix(); the ONLY difference
between them is the tau correction, which isolates its effect in the comparison.
"""

import math
from typing import Dict, Tuple

from backtest.engine import MatchContext, predict_match

MAX_GOALS = 10          # score matrix truncation (P(>10 goals) is negligible)
DC_RHO = -0.13          # Dixon-Coles low-score dependence (typical football value)
_STRENGTH_CLAMP = (0.25, 3.0)   # guard early-season extremes
_MIN_LAMBDA = 0.15


def baseline_model(ctx: MatchContext) -> Dict[str, float]:
    """Current model — delegates to the analyzers via the engine."""
    return predict_match(ctx.scored)


# ── shared strength maths ─────────────────────────────────────────────────────

def _clamp(x: float) -> float:
    lo, hi = _STRENGTH_CLAMP
    return min(hi, max(lo, x))


def _rate(goals: int, matches: int, fallback: float) -> float:
    return goals / matches if matches > 0 else fallback


def _expected_goals(ctx: MatchContext) -> Tuple[float, float]:
    """
    Expected goals for home and away using attack/defence strengths relative to
    the league's home/away baselines. Point-in-time: everything comes from the
    pre-match context.
    """
    lh = max(0.3, ctx.lg_home_avg)   # league avg goals a home side scores
    la = max(0.3, ctx.lg_away_avg)   # league avg goals an away side scores

    h_m, h_gf, h_ga = ctx.home_home  # home team, home record
    a_m, a_gf, a_ga = ctx.away_away  # away team, away record

    home_attack = _clamp(_rate(h_gf, h_m, lh) / lh)
    home_defence = _clamp(_rate(h_ga, h_m, la) / la)
    away_attack = _clamp(_rate(a_gf, a_m, la) / la)
    away_defence = _clamp(_rate(a_ga, a_m, lh) / lh)

    lam_home = max(_MIN_LAMBDA, lh * home_attack * away_defence)
    lam_away = max(_MIN_LAMBDA, la * away_attack * home_defence)
    return lam_home, lam_away


def _poisson_pmf(k: int, lam: float) -> float:
    return lam ** k * math.exp(-lam) / math.factorial(k)


def _dc_tau(i: int, j: int, lam: float, mu: float, rho: float) -> float:
    """Dixon-Coles correction factor for the four low-score cells."""
    if i == 0 and j == 0:
        return 1.0 - lam * mu * rho
    if i == 0 and j == 1:
        return 1.0 + lam * rho
    if i == 1 and j == 0:
        return 1.0 + mu * rho
    if i == 1 and j == 1:
        return 1.0 - rho
    return 1.0


def _score_matrix(lam_home: float, lam_away: float, rho: float = 0.0):
    """
    Joint P(home=i, away=j) matrix. rho=0 -> independent Poisson;
    rho!=0 -> Dixon-Coles corrected (and renormalised).
    """
    home_pmf = [_poisson_pmf(i, lam_home) for i in range(MAX_GOALS + 1)]
    away_pmf = [_poisson_pmf(j, lam_away) for j in range(MAX_GOALS + 1)]

    matrix = [[home_pmf[i] * away_pmf[j] for j in range(MAX_GOALS + 1)]
              for i in range(MAX_GOALS + 1)]

    if rho != 0.0:
        for i in (0, 1):
            for j in (0, 1):
                matrix[i][j] *= _dc_tau(i, j, lam_home, lam_away, rho)

    total = sum(sum(row) for row in matrix)
    if total > 0:
        matrix = [[v / total for v in row] for row in matrix]
    return matrix


def _markets_from_matrix(matrix) -> Dict[str, float]:
    """Derive all backtested markets from a joint score matrix."""
    over_1_5 = over_2_5 = over_3_5 = btts_yes = 0.0
    p1 = pX = p2 = 0.0
    for i, row in enumerate(matrix):
        for j, p in enumerate(row):
            total = i + j
            if total > 1.5:
                over_1_5 += p
            if total > 2.5:
                over_2_5 += p
            if total > 3.5:
                over_3_5 += p
            if i >= 1 and j >= 1:
                btts_yes += p
            if i > j:
                p1 += p
            elif i == j:
                pX += p
            else:
                p2 += p
    return {
        "over_1_5": over_1_5,
        "over_2_5": over_2_5,
        "over_3_5": over_3_5,
        "btts_yes": btts_yes,
        "result_1": p1,
        "result_X": pX,
        "result_2": p2,
    }


def poisson_strength_model(ctx: MatchContext) -> Dict[str, float]:
    """Independent-Poisson strength model (attack x defence x home/away baseline)."""
    lam_home, lam_away = _expected_goals(ctx)
    return _markets_from_matrix(_score_matrix(lam_home, lam_away, rho=0.0))


def dixon_coles_model(ctx: MatchContext, rho: float = DC_RHO) -> Dict[str, float]:
    """Strength model + Dixon-Coles low-score correlation correction."""
    lam_home, lam_away = _expected_goals(ctx)
    return _markets_from_matrix(_score_matrix(lam_home, lam_away, rho=rho))


# Registry used by the comparison runner (insertion order = display order).
MODELS = {
    "Baseline (attuale)": baseline_model,
    "Poisson forze": poisson_strength_model,
    "Dixon-Coles": dixon_coles_model,
}
