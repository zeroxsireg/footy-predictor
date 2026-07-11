"""
Player-level booking model: P(this player gets a yellow) for each player who
takes the field.

Signals (all point-in-time): the player's own booking rate (shrunk toward the
league rate for their POSITION — defenders/midfielders get booked more than
forwards/keepers), and the REFEREE's strictness. An online recalibration keeps
the average predicted bookings in line with reality.

Evaluated as a probabilistic forecast (Brier/calibration) AND as a ranking:
does the model put the actually-booked players near the top?
"""

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List

from backtest.advanced import _to_days
from backtest.metrics import BinaryMarketResult, score_binary

_P_CLAMP = (0.01, 0.9)
_REF_CLAMP = (0.6, 1.6)


@dataclass
class PlayerStat:
    apps: int = 0
    yellows: int = 0
    fouls_sum: float = 0.0
    fouls_apps: int = 0     # appearances with foul data (coverage ~50%)

    def update(self, booked: int, fouls=None) -> None:
        self.apps += 1
        self.yellows += booked
        if fouls is not None:
            self.fouls_sum += fouls
            self.fouls_apps += 1


@dataclass
class RefStat:
    matches: int = 0
    cards: int = 0

    def update(self, total_cards: int) -> None:
        self.matches += 1
        self.cards += total_cards


@dataclass
class PlayerCardsReport:
    n_pairs: int
    n_matches: int
    base_rate: float
    booked: BinaryMarketResult
    mean_p_booked: float          # discrimination: avg prob on players who WERE booked
    mean_p_unbooked: float        # ... vs those who were not
    avg_expected: float           # expected bookings per match
    avg_actual: float
    precision_at_k: float         # of the k highest-prob players, share actually booked


def _clamp(x, lo, hi):
    return min(hi, max(lo, x))


def _ref_name(raw) -> str:
    return str(raw).split(",")[0].strip() if raw else ""


def iter_player_predictions(
    fixtures: List[Dict], players_map: Dict[str, List[Dict]], *,
    xi: float = 0.0, k: float = 4.0, ref_k: float = 8.0, min_apps: int = 3,
    score_seasons: set | None = None,
):
    """
    Point-in-time generator: per in-scope match, yields the booking probability
    for each player with enough history. Single source of truth for both the
    backtest and the prediction card.
    """
    ordered = sorted(fixtures, key=lambda r: (r["date"], r["fixture_id"]))
    ordered = [r for r in ordered if r.get("status") == "FT" and str(r["fixture_id"]) in players_map]
    if not ordered:
        return

    players: Dict[int, PlayerStat] = {}
    positions: Dict[str, PlayerStat] = {}
    refs: Dict[str, RefStat] = {}
    lg_yellows = lg_apps = 0
    lg_cards = lg_matches = 0
    lg_fouls_sum = 0.0
    lg_fouls_apps = 0
    recal_pred = recal_act = 0.0

    for rec in ordered:
        roster = players_map[str(rec["fixture_id"])]
        played = [p for p in roster if p.get("minutes")]
        total_cards = sum(1 for p in played if (p.get("yellow") or 0) >= 1)
        ref = _ref_name(rec.get("referee"))
        in_scope = score_seasons is None or rec.get("season") in score_seasons

        if in_scope:
            base_rate = (lg_yellows / lg_apps) if lg_apps else 0.15
            lg_card_avg = (lg_cards / lg_matches) if lg_matches else 4.0
            if ref and refs.get(ref) and refs[ref].matches > 0:
                ref_rate = (refs[ref].cards + ref_k * lg_card_avg) / (refs[ref].matches + ref_k)
                ref_factor = _clamp(ref_rate / lg_card_avg, *_REF_CLAMP)
            else:
                ref_factor = 1.0
            recal = _clamp(recal_act / recal_pred, 0.7, 1.3) if recal_pred > 0 else 1.0
            lg_fouls_avg = (lg_fouls_sum / lg_fouls_apps) if lg_fouls_apps else 0.0

            rows = []
            for p in played:
                pid = p.get("player_id")
                ps = players.get(pid)
                if pid is None or ps is None or ps.apps < min_apps:
                    continue
                pos = p.get("position") or "?"
                pos_stat = positions.get(pos)
                pos_base = ((pos_stat.yellows + 20 * base_rate) / (pos_stat.apps + 20)
                            if pos_stat else base_rate)
                player_rate = (ps.yellows + k * pos_base) / (ps.apps + k)
                if ps.fouls_apps >= 3 and lg_fouls_avg > 0:
                    fr = (ps.fouls_sum + 5 * lg_fouls_avg) / (ps.fouls_apps + 5)
                    fouls_factor = _clamp(fr / lg_fouls_avg, 0.6, 1.6)
                else:
                    fouls_factor = 1.0
                raw = player_rate * ref_factor * fouls_factor
                prob = _clamp(raw * recal, *_P_CLAMP)
                booked = 1 if (p.get("yellow") or 0) >= 1 else 0
                rows.append({"player_id": pid, "name": p.get("name"),
                             "team_id": p.get("team_id"), "position": pos,
                             "prob": prob, "booked": booked})
                recal_pred += raw
                recal_act += booked
            if rows:
                yield {"fixture_id": rec["fixture_id"], "in_scope": True, "players": rows}

        # ── updates (after prediction) ──
        for p in played:
            pid = p.get("player_id")
            booked = 1 if (p.get("yellow") or 0) >= 1 else 0
            pos = p.get("position") or "?"
            fouls = p.get("fouls")
            if pid is not None:
                players.setdefault(pid, PlayerStat()).update(booked, fouls)
            positions.setdefault(pos, PlayerStat()).update(booked)
            lg_yellows += booked
            lg_apps += 1
            if fouls is not None:
                lg_fouls_sum += fouls
                lg_fouls_apps += 1
        if ref:
            refs.setdefault(ref, RefStat()).update(total_cards)
        lg_cards += total_cards
        lg_matches += 1


def run_player_cards_backtest(
    fixtures: List[Dict], players_map: Dict[str, List[Dict]], *,
    xi: float = 0.0, k: float = 4.0, ref_k: float = 8.0, min_apps: int = 3,
    score_seasons: set | None = None,
) -> PlayerCardsReport:
    pairs: List[tuple] = []
    p_booked: List[float] = []
    p_unbooked: List[float] = []
    exp_list: List[float] = []
    act_list: List[float] = []
    prec_num = prec_den = 0.0
    n_matches = 0

    for pred in iter_player_predictions(
        fixtures, players_map, xi=xi, k=k, ref_k=ref_k, min_apps=min_apps,
        score_seasons=score_seasons,
    ):
        rows = pred["players"]
        n_matches += 1
        for r in rows:
            pairs.append((r["prob"], r["booked"]))
            (p_booked if r["booked"] else p_unbooked).append(r["prob"])
        exp_list.append(sum(r["prob"] for r in rows))
        act_list.append(sum(r["booked"] for r in rows))
        kk = sum(r["booked"] for r in rows)
        if kk > 0:
            top = sorted(rows, key=lambda x: x["prob"], reverse=True)[:kk]
            prec_num += sum(r["booked"] for r in top)
            prec_den += kk

    return PlayerCardsReport(
        n_pairs=len(pairs), n_matches=n_matches,
        base_rate=round(sum(b for _, b in pairs) / len(pairs), 4) if pairs else 0.0,
        booked=score_binary("Giocatore ammonito", pairs),
        mean_p_booked=round(sum(p_booked) / len(p_booked), 4) if p_booked else 0.0,
        mean_p_unbooked=round(sum(p_unbooked) / len(p_unbooked), 4) if p_unbooked else 0.0,
        avg_expected=round(sum(exp_list) / len(exp_list), 2) if exp_list else 0.0,
        avg_actual=round(sum(act_list) / len(act_list), 2) if act_list else 0.0,
        precision_at_k=round(prec_num / prec_den, 4) if prec_den else 0.0,
    )
