"""Pure evaluation of a TIP_CATALOG key against a final score (same definitions as core.tips)."""

from .contracts import TIP_CATALOG


def _atom(key: str, h: int, a: int) -> bool:
    tot = h + a
    if key in ("R_1", "R_X", "R_2"):
        return key[2] == ("1" if h > a else "2" if a > h else "X")
    if key.startswith("DC_"):
        return {"1X": h >= a, "X2": a >= h, "12": h != a}[key[3:]]
    if key in ("GG", "NG"):
        return (h >= 1 and a >= 1) == (key == "GG")
    if key.startswith("MG"):
        _, lo, hi = key.split("_")
        goals = {"MGT": tot, "MGH": h, "MGA": a}[key.split("_")[0]]
        return int(lo) <= goals <= int(hi)
    parts = key.split("_")
    goals = tot
    if parts[0] in ("HOME", "AWAY"):
        goals = h if parts[0] == "HOME" else a
        parts = parts[1:]
    line = float(parts[1])
    return goals > line if parts[0] == "OV" else goals < line


def tip_outcome(key: str, home_goals: int, away_goals: int) -> bool:
    """True if the tip `key` wins with this final score. Combos are AND of their two atoms."""
    if key not in TIP_CATALOG:
        raise KeyError(f"unknown tip key {key}")
    return all(_atom(k, home_goals, away_goals) for k in key.split("+"))


__all__ = ["tip_outcome"]
