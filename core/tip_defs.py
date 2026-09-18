"""
Single definition of every TIP_CATALOG market as a predicate on the final score (i, j)
= (home goals, away goals). Used both to sum a probability matrix (core/tips.py) and to
grade a real result (reliability backtest), so the two can never disagree (SSOT).

Rules: Over N.5 = total goals > N.5; MGT_a_b = a <= i+j <= b; MGH_a_b = a <= i <= b;
MGA_a_b = a <= j <= b; HOME_OV_x = i > x; combos ("A+B") are joint events on the same match.
"""

from typing import Callable, Dict, List

from core.contracts import TIP_CATALOG

Predicate = Callable[[int, int], bool]


def _atom(key: str) -> Predicate:
    parts = key.split("_")
    head = parts[0]
    if head == "R":
        return {"1": lambda i, j: i > j, "X": lambda i, j: i == j,
                "2": lambda i, j: i < j}[parts[1]]
    if head == "DC":
        return {"1X": lambda i, j: i >= j, "X2": lambda i, j: i <= j,
                "12": lambda i, j: i != j}[parts[1]]
    if head in ("OV", "UN"):
        line = float(parts[1])
        return (lambda i, j: i + j > line) if head == "OV" else (lambda i, j: i + j < line)
    if head in ("HOME", "AWAY"):
        line = float(parts[2])
        pick = (lambda i, j: i) if head == "HOME" else (lambda i, j: j)
        if parts[1] == "OV":
            return lambda i, j: pick(i, j) > line
        return lambda i, j: pick(i, j) < line
    if key == "GG":
        return lambda i, j: i > 0 and j > 0
    if key == "NG":
        return lambda i, j: i == 0 or j == 0
    if head in ("MGT", "MGH", "MGA"):
        lo, hi = int(parts[1]), int(parts[2])
        val = {"MGT": lambda i, j: i + j, "MGH": lambda i, j: i,
               "MGA": lambda i, j: j}[head]
        return lambda i, j: lo <= val(i, j) <= hi
    raise KeyError(key)


def _build(key: str) -> Predicate:
    if "+" in key:
        a, b = (_atom(part) for part in key.split("+"))
        return lambda i, j: a(i, j) and b(i, j)
    return _atom(key)


TIP_PREDICATES: Dict[str, Predicate] = {key: _build(key) for key in TIP_CATALOG}


def tip_probability(matrix: List[List[float]], key: str) -> float:
    """Sum of the matrix cells where the market is true."""
    pred = TIP_PREDICATES[key]
    return sum(p for i, row in enumerate(matrix) for j, p in enumerate(row) if pred(i, j))
