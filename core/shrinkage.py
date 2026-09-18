"""
Bayesian shrinkage helpers and league-average priors for the pre-match
goals / 1X2 estimators (SSOT: used by analyzers/goals_analyzer.py and
analyzers/result_analyzer.py, which the backtest consumes as-is).

With few games played, raw season averages are noisy (e.g. 4/4 games with both
teams scoring -> 100%). Shrinkage pulls the estimate toward the league average
with a weight that grows with the number of games played:

    estimate = (observed_total + k * prior) / (n + k)
"""

# League-average priors (rounded, averaged over Serie A / La Liga / PL / Bundesliga 2023-25).
PRIOR_GOALS_PER_TEAM_GAME = 1.35
PRIOR_SCORE_RATE = 0.74          # P(team scores at least once in a match)
PRIOR_WIN_RATE = 0.33
PRIOR_DRAW_RATE = 0.26
PRIOR_POINTS_PER_GAME = 1.37
PRIOR_GOAL_DIFF_PER_GAME = 0.0

# Pseudo-matches of prior weight (fitted on Serie A 2024/2025 by Brier/RPS, confirmed unchanged on La Liga).
K_GOALS = 16.0
K_SCORE_RATE = 4.0
K_RESULT = 8.0

# Final probability clamp: never claim certainty from a small sample.
P_MIN, P_MAX = 0.03, 0.97


def shrink(total: float, n: float, prior: float, k: float) -> float:
    """Posterior-mean style estimate of a per-game rate."""
    return (total + k * prior) / (n + k) if (n + k) > 0 else prior


def clamp_probability(p: float) -> float:
    return min(P_MAX, max(P_MIN, p))
