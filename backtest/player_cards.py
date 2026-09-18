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

from dataclasses import dataclass, replace
from typing import Dict, List

from backtest.metrics import BinaryMarketResult, score_binary
from core.player_card_model import DEFAULT_PARAMS, PlayerCardModel, ref_name

_ref_name = ref_name  # backward-compatible alias (SSOT lives in core)


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


def iter_player_predictions(
    fixtures: List[Dict], players_map: Dict[str, List[Dict]], *,
    xi: float = 0.0, k: float = DEFAULT_PARAMS.k, ref_k: float = 8.0, min_apps: int = 3,
    score_seasons: set | None = None,
):
    """
    Point-in-time generator: per in-scope match, yields the booking probability
    for each player with enough history (snapshot -> predict -> update).
    The estimator itself lives in core/player_card_model.py (SSOT).
    """
    ordered = sorted(fixtures, key=lambda r: (r["date"], r["fixture_id"]))
    ordered = [r for r in ordered if r.get("status") == "FT" and str(r["fixture_id"]) in players_map]
    model = PlayerCardModel(replace(DEFAULT_PARAMS, k=k, ref_k=ref_k, min_apps=min_apps))

    for rec in ordered:
        played = [p for p in players_map[str(rec["fixture_id"])] if p.get("minutes")]
        referee = ref_name(rec.get("referee"))
        if score_seasons is None or rec.get("season") in score_seasons:
            rows = model.predict_match(played, referee)
            if rows:
                yield {"fixture_id": rec["fixture_id"], "in_scope": True, "players": rows}
        model.update_match(played, referee)  # only after the prediction


def run_player_cards_backtest(
    fixtures: List[Dict], players_map: Dict[str, List[Dict]], *,
    xi: float = 0.0, k: float = DEFAULT_PARAMS.k, ref_k: float = 8.0, min_apps: int = 3,
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
