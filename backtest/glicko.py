"""
Glicko-2 rating system adapted for football, as a second 1X2 model to ensemble
with the Poisson-strength model.

Why a rating model *in addition* to Poisson: it captures team strength from the
win/draw/loss sequence (with margin-of-victory) rather than from goal averages,
so its errors are partly independent — exactly what makes an ensemble help.

Design:
  - Standard Glicko-2 update (rating r, deviation RD, volatility sigma), one
    match per rating period (a common, well-behaved simplification).
  - Global home advantage applied to the home rating when computing the
    expected score (for both prediction and update).
  - Margin-of-victory: a gentle multiplier on the update so decisive wins move
    ratings more than narrow ones (draws keep the standard update).
  - 1X2 probabilities: the home-adjusted rating gap is mapped to a goal
    supremacy and fed through the shared Poisson score-matrix, so draws emerge
    naturally and the output is directly comparable to the other models.

Reference: Glickman, "Example of the Glicko-2 system" (2013).
"""

import math
from dataclasses import dataclass
from typing import Dict

from backtest.models import _score_matrix, _markets_from_matrix

SCALE = 173.7178
TAU = 0.5           # system constant (constrains volatility change)
EPS = 1e-6

DEFAULT_R = 1500.0
DEFAULT_RD = 350.0
DEFAULT_VOL = 0.06

# Prediction mapping (rating points -> expected goals)
HOME_ADV = 65.0     # home advantage in rating points
GOALS_PER_POINT = 0.006   # goal supremacy per rating-point gap
DEFAULT_TOTAL = 2.6       # fallback league avg total goals


@dataclass
class GlickoRating:
    r: float = DEFAULT_R
    rd: float = DEFAULT_RD
    vol: float = DEFAULT_VOL


def _g(phi: float) -> float:
    return 1.0 / math.sqrt(1.0 + 3.0 * phi * phi / (math.pi * math.pi))


def _expected(mu: float, mu_j: float, phi_j: float) -> float:
    return 1.0 / (1.0 + math.exp(-_g(phi_j) * (mu - mu_j)))


def mov_multiplier(goal_diff: int) -> float:
    """Gentle margin-of-victory weight: draws/1-goal -> 1.0, bigger wins -> more."""
    return 1.0 + 0.5 * math.log(max(1, abs(goal_diff)))


def _solve_volatility(phi: float, v: float, delta: float, sigma: float) -> float:
    """Glicko-2 step 5: illinois-method solve for the new volatility."""
    a = math.log(sigma * sigma)
    delta2 = delta * delta
    phi2 = phi * phi

    def f(x: float) -> float:
        ex = math.exp(x)
        num = ex * (delta2 - phi2 - v - ex)
        den = 2.0 * (phi2 + v + ex) ** 2
        return num / den - (x - a) / (TAU * TAU)

    A = a
    if delta2 > phi2 + v:
        B = math.log(delta2 - phi2 - v)
    else:
        k = 1
        while f(a - k * TAU) < 0:
            k += 1
        B = a - k * TAU

    fA, fB = f(A), f(B)
    while abs(B - A) > EPS:
        C = A + (A - B) * fA / (fB - fA)
        fC = f(C)
        if fC * fB <= 0:
            A, fA = B, fB
        else:
            fA = fA / 2.0
        B, fB = C, fC
    return math.exp(A / 2.0)


def updated(rating: GlickoRating, opp: GlickoRating, score: float,
            mov: float = 1.0, rating_bonus: float = 0.0) -> GlickoRating:
    """
    Return `rating` updated after one match vs `opp`.

    score: 1.0 win / 0.5 draw / 0.0 loss (from `rating`'s perspective).
    mov: margin-of-victory multiplier on the update magnitude.
    rating_bonus: added to this team's rating for the expected-score calc
                  (home advantage; positive for home, negative for away).
    """
    mu = (rating.r + rating_bonus - 1500.0) / SCALE
    phi = rating.rd / SCALE
    mu_j = (opp.r - 1500.0) / SCALE
    phi_j = opp.rd / SCALE

    gj = _g(phi_j)
    e = _expected(mu, mu_j, phi_j)
    v = 1.0 / (gj * gj * e * (1.0 - e))
    delta = v * gj * (score - e) * mov

    sigma_new = _solve_volatility(phi, v, delta, rating.vol)
    phi_star = math.sqrt(phi * phi + sigma_new * sigma_new)
    phi_new = 1.0 / math.sqrt(1.0 / (phi_star * phi_star) + 1.0 / v)
    mu_new = mu + phi_new * phi_new * gj * (score - e) * mov

    return GlickoRating(
        r=SCALE * mu_new + 1500.0,
        rd=SCALE * phi_new,
        vol=sigma_new,
    )


def predict_1x2(
    home: GlickoRating, away: GlickoRating,
    total_goals: float = DEFAULT_TOTAL,
    home_adv: float = HOME_ADV, goals_per_point: float = GOALS_PER_POINT,
) -> Dict[str, float]:
    """1X2 (+ goals) probabilities from the home-adjusted rating gap."""
    supremacy = goals_per_point * ((home.r + home_adv) - away.r)
    lam_home = max(0.15, (total_goals + supremacy) / 2.0)
    lam_away = max(0.15, (total_goals - supremacy) / 2.0)
    return _markets_from_matrix(_score_matrix(lam_home, lam_away))
