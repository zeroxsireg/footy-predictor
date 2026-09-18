"""
Value-bet rules (single bets only): EV filter, ordering and fractional-Kelly sizing.

SSOT for the live path and for the backtests. Rules (.agents/GEMINI.md):
  7. EV = P * odds - 1 must exceed tau (3%).
  8. Fractional Kelly only (0.25 * f*), capped per bet (2% of bankroll).
 11. A pick without a REAL quote and its bookmaker is never a "value" pick.

Caveat: P is the live model's probability. It is currently worse calibrated
than the market (RPS 1X2 0.226 vs 0.189), so EV computed on it is optimistic.
"""

from typing import List, Optional

from .edge_calculator import KELLY_FRACTION, calculate_edge, calculate_ev, calculate_kelly

MIN_EV_THRESHOLD = 0.03      # tau, rule 7 (SSOT: value_engine imports it from here)
MAX_STAKE_FRACTION = 0.025   # per-bet cap on bankroll, rule 8
MAX_DAILY_FRACTION = 0.12    # cap on the total bankroll fraction staked per day/strategy
BREAKER_KELLY_FRACTION = 0.125   # Kelly multiplier while the circuit breaker is active
BREAKER_DRAWDOWN = 0.20      # drawdown from high-water mark that trips the breaker
INITIAL_BANKROLL = 50.00     # paper bankroll per strategy
STAKE_STEP = 0.05            # currency rounding
MIN_STAKE = 0.10             # below this the bet is discarded
MAX_DAILY_PICKS = 3


def ev_fraction(prob: float, odds: float) -> float:
    """EV as a fraction of stake (0.03 = +3%), via the edge_calculator SSOT."""
    return calculate_ev(prob, odds) / 100.0


def stake_fraction(prob: float, odds: float, *, kelly_fraction: float = KELLY_FRACTION,
                   cap: float = MAX_STAKE_FRACTION) -> float:
    """Fractional Kelly stake as a fraction of bankroll, capped."""
    return min(kelly_fraction * calculate_kelly(prob, odds), cap)


def annotate_value(pick, tau: float = MIN_EV_THRESHOLD) -> bool:
    """
    Fill edge/ev_percent/kelly_quarter/stake_fraction/verdict on a DailyPick.

    Returns True only for a value pick (real odds + bookmaker + EV > tau).
    Picks without real odds are left untouched and never qualify.
    """
    odds = pick.real_odds
    if not odds or odds <= 1.0 or not pick.bookmaker:
        return False
    prob = pick.percentage / 100.0
    pick.edge = round(calculate_edge(prob, odds), 4)      # vs gross implied prob
    pick.ev_percent = calculate_ev(prob, odds)
    pick.kelly_quarter = round(KELLY_FRACTION * calculate_kelly(prob, odds), 4)
    pick.stake_fraction = round(stake_fraction(prob, odds), 4)
    is_value = ev_fraction(prob, odds) > tau and pick.stake_fraction > 0
    pick.verdict = "VALUE" if is_value else "PASS"
    return is_value


def select_value_picks(picks: List, tau: float = MIN_EV_THRESHOLD,
                       limit: Optional[int] = None) -> List:
    """Single bets with EV > tau, best EV first. Includes 'Player Card - ...' picks."""
    value = [p for p in picks if annotate_value(p, tau)]
    value.sort(key=lambda p: p.ev_percent, reverse=True)
    return value[:limit] if limit else value
