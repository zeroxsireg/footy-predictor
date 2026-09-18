"""
Daily tip list and 2-3 leg multiples (tipster style, Serie A). Pure logic, no I/O.

Anti-redundancy rule (deterministic): at most ONE tip per (fixture, family). Within a family the
most probable tip wins (ties: key alphabetical). Example: DC_1X and DC_X2 (both "doublechance")
never coexist; a combo like DC_X2+OV_1.5 is family "combo", so at most one combo per fixture.
A combo is also dropped when one of its components (e.g. DC_X2 for DC_X2+OV_1.5) is already
chosen on that fixture (the component is more probable, hence processed first). Then the fixture keeps its `max_per_fixture` most probable survivors.

EV exists only where a real TipQuote exists: EV = p * odds - 1 (rules 6/7). No quote -> ev=None,
conviene=None (the user compares by hand with min_odds). conviene = real odds >= min_odds.

Multiples: legs from DIFFERENT fixtures, probability = product of leg probabilities (independent
matches). Caveat: the multiple's min_odds equals the product of leg min_odds only if the real
quote of every leg respects its own min; and a multiple multiplies the bookmaker margin of each
leg, so its real value is usually lower than the fair-odds arithmetic suggests.
"""

from dataclasses import dataclass
from itertools import combinations
from typing import Dict, List, Optional

from .contracts import MAX_MULTIPLE_LEGS, TIP_MIN_EDGE, Multiple, Tip, TipQuote


@dataclass(frozen=True)
class SelectedTip:
    tip: Tip
    quote: Optional[TipQuote] = None
    ev: Optional[float] = None
    conviene: Optional[bool] = None     # None = no real quote available


def _decorate(tip: Tip, quote: Optional[TipQuote]) -> SelectedTip:
    if quote is None:
        return SelectedTip(tip)
    return SelectedTip(tip, quote, tip.probability * quote.odds - 1.0, quote.odds >= tip.min_odds)


def _order(t: Tip):
    return (-t.probability, t.fixture_id, t.key)


def select_daily_tips(tips_by_fixture: Dict[int, List[Tip]],
                      quotes: Optional[Dict[int, Dict[str, TipQuote]]] = None, *,
                      min_prob: float = 0.75, max_per_fixture: int = 2, top_n: int = 10,
                      exclude_low_reliability: bool = True) -> List[SelectedTip]:
    """Most probable tips of the day, sorted by probability desc (ties: fixture id, key)."""
    quotes = quotes or {}
    chosen: List[Tip] = []
    for fid, tips in tips_by_fixture.items():
        best: Dict[str, Tip] = {}
        for t in sorted(tips, key=lambda x: (-x.probability, x.key)):
            if t.probability < min_prob or (exclude_low_reliability and t.reliability == "bassa"):
                continue
            if t.family in best or any(k in {x.key for x in best.values()} for k in t.key.split("+")[:2]
                                       if "+" in t.key):
                continue                        # one per family; combos never repeat a component
            best[t.family] = t                  # first seen = most probable
        chosen.extend(sorted(best.values(), key=_order)[:max_per_fixture])
    chosen.sort(key=_order)
    return [_decorate(t, quotes.get(t.fixture_id, {}).get(t.key)) for t in chosen[:top_n]]


def build_multiples(selected: List[SelectedTip], *, max_legs: int = MAX_MULTIPLE_LEGS,
                    min_legs: int = 2, min_prob: float = 0.5, top_n: int = 5) -> List[Multiple]:
    """2..3 legs from different fixtures; hard cap MAX_MULTIPLE_LEGS whatever max_legs says."""
    max_legs = min(max_legs, MAX_MULTIPLE_LEGS)
    tips = [s.tip for s in selected]
    out: List[Multiple] = []
    for n in range(max(min_legs, 2), max_legs + 1):
        for legs in combinations(tips, n):
            if len({t.fixture_id for t in legs}) < n:
                continue
            p = 1.0
            for t in legs:
                p *= t.probability
            if p < min_prob or p <= 0:
                continue
            fair = 1.0 / p
            out.append(Multiple(tuple(legs), p, fair, fair * (1.0 + TIP_MIN_EDGE)))
    out.sort(key=lambda m: (-m.probability, tuple((t.fixture_id, t.key) for t in m.legs)))
    return out[:top_n]
