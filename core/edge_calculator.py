"""
Edge Calculator - Converte probabilità in decisioni di scommessa ottimali.

Implementa:
- Calcolo edge vs probabilità implicita bookmaker
- Expected Value (EV)
- Kelly Criterion (con Kelly frazionato 1/4 raccomandato)
- Extremizing (Good Judgment Project method)
- Brier Score tracking

Riferimento: market-mechanics-betting skill
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

# ─── Soglie standard ────────────────────────────────────────────────────────
MIN_EDGE_THRESHOLD = 0.05   # 5% minimum edge per scommesse sportive
KELLY_FRACTION = 0.25       # Quarter Kelly raccomandato (riduce variance del 75%)
EXTREMIZING_FACTOR = 1.3    # Fattore moderato (Good Judgment Project default)


# ─── Data classes ───────────────────────────────────────────────────────────

@dataclass
class BetDecision:
    """Decisione completa su una singola scommessa."""
    our_probability: float        # 0.0 – 1.0 (nostra stima)
    market_probability: float     # 0.0 – 1.0 (implicita dalle quote)
    decimal_odds: float           # es. 2.10
    edge: float                   # our_prob - market_prob  (positivo = value)
    ev_percent: float             # Expected Value come % dell'importo scommesso
    kelly_full: float             # Kelly fraction pieno  (0.0 – 1.0)
    kelly_quarter: float          # Kelly /4 raccomandato
    verdict: str                  # "BET" | "VALUE" | "PASS"
    verdict_emoji: str
    reasoning: str


# ─── Funzioni core ──────────────────────────────────────────────────────────

def implied_probability(decimal_odds: float) -> float:
    """
    Probabilità implicita da quota decimale.
    Nota: include il margine del bookmaker (overround).
    """
    if decimal_odds <= 1.0:
        return 1.0
    return 1.0 / decimal_odds


def calculate_edge(our_probability: float, decimal_odds: float) -> float:
    """
    Edge = nostra probabilità - probabilità implicita bookmaker.

    Positivo → abbiamo un vantaggio sul mercato.
    Negativo → il mercato ci valuta peggio della quota.
    """
    return our_probability - implied_probability(decimal_odds)


def calculate_ev(our_probability: float, decimal_odds: float) -> float:
    """
    Expected Value come percentuale dell'importo scommesso.

    EV = (p × profitto_netto) - (q × stake)
       = p × (odds - 1) - (1 - p)

    Restituisce valore in percentuale (es. +12.4 = +12.4%).
    """
    net_odds = decimal_odds - 1.0
    ev = our_probability * net_odds - (1.0 - our_probability)
    return round(ev * 100, 2)


def calculate_kelly(our_probability: float, decimal_odds: float) -> float:
    """
    Kelly Criterion: frazione ottimale del bankroll da scommettere.

    f* = (b·p − q) / b
    dove b = net odds, p = win prob, q = 1-p

    Restituisce valore 0.0 – 1.0 (clampato a 0 se negativo).
    """
    b = decimal_odds - 1.0
    p = our_probability
    q = 1.0 - p
    if b <= 0:
        return 0.0
    kelly = (b * p - q) / b
    return max(0.0, round(kelly, 4))


def extremize(probability: float, factor: float = EXTREMIZING_FACTOR) -> float:
    """
    Extremizing: sposta la probabilità lontano dal 50%.

    Formula: 0.5 + (prob - 0.5) × factor

    Utile quando si aggregano più segnali indipendenti (Good Judgment Project).
    Factor 1.3 = moderato (default), 1.5 = forte (segnali molto indipendenti).

    Input/output: 0.0 – 1.0 (clampato a [0.01, 0.99]).
    """
    extremized = 0.5 + (probability - 0.5) * factor
    return max(0.01, min(0.99, round(extremized, 4)))


def evaluate_bet(
    our_probability_pct: float,
    decimal_odds: float,
    min_edge: float = MIN_EDGE_THRESHOLD,
    kelly_fraction: float = KELLY_FRACTION,
) -> BetDecision:
    """
    Valutazione completa di una scommessa.

    Args:
        our_probability_pct: nostra probabilità in percentuale (es. 72.0)
        decimal_odds:         quota decimale bookmaker (es. 2.10)
        min_edge:             soglia minima edge per "BET" (default 5%)
        kelly_fraction:       frazione Kelly (default 1/4)

    Returns:
        BetDecision con verdict "BET" / "VALUE" / "PASS"
    """
    p = our_probability_pct / 100.0
    market_p = implied_probability(decimal_odds)
    edge = calculate_edge(p, decimal_odds)
    ev = calculate_ev(p, decimal_odds)
    kelly_full = calculate_kelly(p, decimal_odds)
    kelly_q = round(kelly_full * kelly_fraction, 4)

    if edge >= min_edge and kelly_full > 0:
        verdict = "BET"
        verdict_emoji = "✅"
        reasoning = (
            f"Edge +{edge*100:.1f}% sopra soglia {min_edge*100:.0f}% "
            f"• EV +{ev:.1f}% • Kelly ¼: {kelly_q*100:.1f}% bankroll"
        )
    elif edge > 0:
        verdict = "VALUE"
        verdict_emoji = "⚡"
        reasoning = (
            f"Edge +{edge*100:.1f}% (sotto soglia {min_edge*100:.0f}%) "
            f"• EV +{ev:.1f}% • Kelly troppo piccolo"
        )
    else:
        verdict = "PASS"
        verdict_emoji = "❌"
        reasoning = (
            f"Nessun edge ({edge*100:.1f}%) — mercato prezza "
            f"{market_p*100:.1f}% vs nostro {our_probability_pct:.1f}%"
        )

    return BetDecision(
        our_probability=p,
        market_probability=market_p,
        decimal_odds=decimal_odds,
        edge=edge,
        ev_percent=ev,
        kelly_full=kelly_full,
        kelly_quarter=kelly_q,
        verdict=verdict,
        verdict_emoji=verdict_emoji,
        reasoning=reasoning,
    )


# ─── Brier Score ─────────────────────────────────────────────────────────────

def brier_score(probability: float, outcome: int) -> float:
    """
    Brier Score per una singola previsione.
    Brier = (p - o)²  →  0 = perfetto, 1 = pessimo

    Args:
        probability: nostra probabilità (0.0 – 1.0)
        outcome:     risultato reale (1 = evento avvenuto, 0 = no)
    """
    return round((probability - outcome) ** 2, 4)


def brier_score_average(predictions: list[tuple[float, int]]) -> float:
    """
    Media Brier Score su N previsioni.

    Args:
        predictions: lista di tuple (probability, outcome)

    Interpretazione:
        < 0.10  Eccellente
        0.10-0.15  Buono
        0.15-0.20  Nella media
        > 0.25  Peggio del random
    """
    if not predictions:
        return 0.0
    scores = [brier_score(p, o) for p, o in predictions]
    return round(sum(scores) / len(scores), 4)


def brier_skill_score(our_brier: float, baseline_brier: float = 0.25) -> float:
    """
    Brier Skill Score: quanto siamo meglio del random (baseline = 0.25).

    BSS = 1 - (our_brier / baseline_brier)
    BSS = 1.0  → perfetto
    BSS = 0.0  → uguale al baseline
    BSS < 0    → peggio del random
    """
    if baseline_brier == 0:
        return 0.0
    return round(1.0 - (our_brier / baseline_brier), 4)
