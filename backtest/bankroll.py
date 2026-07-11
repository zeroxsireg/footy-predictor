"""
Bankroll simulation: bet the xG model's value selections through a season and
track the money.

Honest scope: only 1X2 and Over/Under 2.5 have historical odds (football-data),
so only these can be simulated. Cards/multigol/BTTS — where the model has real
edge — have no historical odds and cannot be bet here.

Stakes: fractional Kelly on value bets (our prob beats the implied prob by the
edge threshold), capped per bet. Best-available ("max") odds = line shopping.
"""

import difflib
import unicodedata
from typing import Dict, List, Tuple

from core.edge_calculator import calculate_kelly


def _norm(name: str) -> str:
    s = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower()
    for tok in (" fc", " cf", " afc", " cd", " ac ", " ss ", " us ", " calcio", " deportivo"):
        s = s.replace(tok, " ")
    return " ".join(s.split())


def build_fuzzy_index(odds_records: List[Dict], our_names) -> Tuple[Dict, List]:
    """Map football-data team names to our API names via normalized fuzzy match."""
    norm_to_our = {_norm(n): n for n in our_names}
    keys = list(norm_to_our)

    def match(fd_name):
        n = _norm(fd_name)
        if n in norm_to_our:
            return norm_to_our[n]
        m = difflib.get_close_matches(n, keys, n=1, cutoff=0.6)
        return norm_to_our[m[0]] if m else None

    index, unmatched = {}, []
    for r in odds_records:
        h, a = match(r["home"]), match(r["away"])
        if h and a:
            index[(h, a)] = r
        else:
            unmatched.append((r["home"], r["away"]))
    return index, unmatched


def build_top_team_map(
    fixtures: List[Dict], target_season: int, *, top_n: int = 8, min_games: int = 5,
) -> Dict[int, tuple]:
    """
    Point-in-time 'is this a top-team match?' map.

    Ranks teams by points-per-game over all loaded history up to each match
    (multi-season, so it captures the consistently strong clubs), and records
    for every target-season fixture whether home/away are currently top-N.
    """
    ordered = sorted(
        [r for r in fixtures if r.get("status") == "FT"
         and r.get("home_goals") is not None],
        key=lambda r: (r["date"], r["fixture_id"]),
    )
    pts: Dict[int, int] = {}
    games: Dict[int, int] = {}
    out: Dict[int, tuple] = {}

    for rec in ordered:
        hid, aid = rec["home_id"], rec["away_id"]
        ranked = sorted(
            (t for t in pts if games[t] >= min_games),
            key=lambda t: pts[t] / games[t], reverse=True,
        )
        top = set(ranked[:top_n])
        if rec.get("season") == target_season:
            out[rec["fixture_id"]] = (hid in top, aid in top)

        hg, ag = rec["home_goals"], rec["away_goals"]
        for t in (hid, aid):
            games[t] = games.get(t, 0) + 1
            pts.setdefault(t, 0)
        if hg > ag:
            pts[hid] += 3
        elif hg < ag:
            pts[aid] += 3
        else:
            pts[hid] += 1
            pts[aid] += 1
    return out


def simulate(
    predictions: List[Dict], odds_index: Dict, *,
    start: float = 100.0, edge_threshold: float = 0.05,
    kelly_fraction: float = 0.25, max_stake_frac: float = 0.05,
    markets=("1x2", "ou"), top_map: Dict = None, top_mode: str = "any",
) -> Dict:
    """Walk the season in date order, placing fractional-Kelly value bets.

    markets: which markets to bet — "1x2", "ou", or both.
    """
    bankroll = peak = start
    max_dd = 0.0
    n_bets = wins = 0
    staked = 0.0
    trajectory = [start]

    for pred in predictions:
        if top_map is not None:
            h_top, a_top = top_map.get(pred["fixture_id"], (False, False))
            if top_mode == "both" and not (h_top and a_top):
                continue
            if top_mode == "any" and not (h_top or a_top):
                continue
        odds = odds_index.get((pred["home_name"], pred["away_name"]))
        if not odds:
            continue
        hg, ag = pred["home_goals"], pred["away_goals"]
        p = pred["probs"]
        result = "1" if hg > ag else "2" if hg < ag else "X"
        over = (hg + ag) > 2.5

        raw = []
        if "1x2" in markets:
            raw += [
                (odds.get("o1"), p["result_1"], result == "1"),
                (odds.get("ox"), p["result_X"], result == "X"),
                (odds.get("o2"), p["result_2"], result == "2"),
            ]
        if "ou" in markets:
            raw += [
                (odds.get("oover"), p["over_2_5"], over),
                (odds.get("ounder"), 1 - p["over_2_5"], not over),
            ]
        candidates = [(o, pr, w) for o, pr, w in raw if o and o > 1.0]

        for odd, prob, won in candidates:
            if prob - 1.0 / odd <= edge_threshold:
                continue
            kf = calculate_kelly(prob, odd)
            if kf <= 0:
                continue
            stake = min(bankroll * kelly_fraction * kf, bankroll * max_stake_frac)
            if stake <= 0 or bankroll <= 0:
                continue
            n_bets += 1
            staked += stake
            if won:
                bankroll += stake * (odd - 1.0)
                wins += 1
            else:
                bankroll -= stake

        peak = max(peak, bankroll)
        if peak > 0:
            max_dd = max(max_dd, (peak - bankroll) / peak)
        trajectory.append(bankroll)

    profit = bankroll - start
    return {
        "start": start, "final": round(bankroll, 2), "profit": round(profit, 2),
        "n_bets": n_bets, "wins": wins,
        "hit_rate": round(wins / n_bets, 3) if n_bets else 0.0,
        "staked": round(staked, 2),
        "yield": round(profit / staked, 4) if staked else 0.0,
        "max_drawdown": round(max_dd, 3),
        "trajectory": trajectory,
    }
