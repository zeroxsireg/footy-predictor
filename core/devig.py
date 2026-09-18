"""
De-vigging of decimal odds into fair probabilities (sum = 1).

Default is Shin (1993): models the overround as protection against insider trading,
shrinking longshots more than favourites. Measured on 1900 matches: RPS 0.19529 vs
0.19546 proportional (tiny gain, but the theoretically correct choice, rule 7).
"""

from typing import List, Sequence

from scipy.optimize import brentq

SHIN_Z_MIN = 1e-9
SHIN_Z_MAX = 0.4
POWER_K_MAX = 20.0


def _implied(odds: Sequence[float]) -> List[float]:
    if len(odds) < 2 or any(o is None or o <= 1.0 for o in odds):
        raise ValueError("need >= 2 decimal odds, all > 1.0")
    return [1.0 / o for o in odds]


def proportional(odds: Sequence[float]) -> List[float]:
    """Normalise implied probabilities by their sum."""
    pi = _implied(odds)
    beta = sum(pi)
    return [p / beta for p in pi]


def _shin_probs(pi: Sequence[float], beta: float, z: float) -> List[float]:
    return [((z * z + 4.0 * (1.0 - z) * p * p / beta) ** 0.5 - z) / (2.0 * (1.0 - z))
            for p in pi]


def shin(odds: Sequence[float]) -> List[float]:
    """Shin de-vig; z solved with brentq, proportional fallback if no root."""
    pi = _implied(odds)
    beta = sum(pi)
    if beta <= 1.0 + 1e-12:
        return [p / beta for p in pi]

    def f(z: float) -> float:
        return sum(_shin_probs(pi, beta, z)) - 1.0

    try:
        z = brentq(f, SHIN_Z_MIN, SHIN_Z_MAX)
    except ValueError:
        return [p / beta for p in pi]
    probs = _shin_probs(pi, beta, z)
    s = sum(probs)
    return [p / s for p in probs]


def power(odds: Sequence[float]) -> List[float]:
    """Power method: p_i = pi_i ** k with k >= 1 such that the sum is 1."""
    pi = _implied(odds)
    if sum(pi) <= 1.0 + 1e-12:
        return [p / sum(pi) for p in pi]
    try:
        k = brentq(lambda k: sum(p ** k for p in pi) - 1.0, 1.0, POWER_K_MAX)
    except ValueError:
        return proportional(odds)
    return [p ** k for p in pi]
