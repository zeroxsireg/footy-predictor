"""Tests for odds parsing and CLV evaluation."""

import pytest

from backtest.odds_data import parse_odds, index_by_teams, season_code, SERIE_A_ALIASES
from backtest.clv import _devig, evaluate_clv


# ── odds parsing ──────────────────────────────────────────────────────────────

def test_season_code():
    assert season_code(2024) == "2425"
    assert season_code(2023) == "2324"


def test_parse_odds_reads_closing_and_aliases():
    csv_text = (
        "Date,HomeTeam,AwayTeam,FTHG,FTAG,PSCH,PSCD,PSCA,PC>2.5,PC<2.5\n"
        "18/08/2024,Milan,Torino,2,2,1.85,3.60,4.50,1.90,2.00\n"
    )
    recs = parse_odds(csv_text, SERIE_A_ALIASES)
    assert len(recs) == 1
    r = recs[0]
    assert r["home"] == "AC Milan"      # alias applied
    assert r["away"] == "Torino"
    assert r["o1"] == 1.85 and r["ox"] == 3.60 and r["o2"] == 4.50
    assert r["oover"] == 1.90 and r["ounder"] == 2.00


def test_parse_odds_max_source_prefers_best_available():
    csv_text = (
        "Date,HomeTeam,AwayTeam,FTHG,FTAG,PSCH,PSCD,PSCA,MaxCH,MaxCD,MaxCA,"
        "PC>2.5,PC<2.5,MaxC>2.5,MaxC<2.5\n"
        "18/08/2024,Inter,Lecce,3,0,1.30,5.0,9.0,1.36,5.5,11.0,1.85,2.05,1.95,2.15\n"
    )
    r = parse_odds(csv_text, source="max")[0]
    assert r["o1"] == 1.36        # best available, higher than Pinnacle 1.30
    assert r["oover"] == 1.95     # best available over
    sharp = parse_odds(csv_text, source="sharp")[0]
    assert sharp["o1"] == 1.30    # sharp uses Pinnacle


def test_parse_odds_falls_back_to_bet365_when_no_pinnacle():
    csv_text = (
        "Date,HomeTeam,AwayTeam,FTHG,FTAG,B365CH,B365CD,B365CA\n"
        "18/08/2024,Inter,Lecce,3,0,1.30,5.0,9.0\n"
    )
    r = parse_odds(csv_text)[0]
    assert r["o1"] == 1.30
    assert r["oover"] is None   # no O/U columns present


def test_index_by_teams():
    recs = [{"home": "Inter", "away": "Milan", "o1": 2.0}]
    idx = index_by_teams(recs)
    assert idx[("Inter", "Milan")]["o1"] == 2.0


# ── de-vig ────────────────────────────────────────────────────────────────────

def test_devig_sums_to_one():
    probs = _devig(2.0, 3.5, 4.0)
    assert sum(probs) == pytest.approx(1.0)
    assert probs[0] > probs[2]   # shorter odds -> higher prob


# ── CLV evaluation ────────────────────────────────────────────────────────────

def _pred(home, away, hg, ag, p1, pX, p2, pover):
    return {
        "fixture_id": 1, "date": "2024-01-01", "home_name": home, "away_name": away,
        "home_goals": hg, "away_goals": ag,
        "probs": {"result_1": p1, "result_X": pX, "result_2": p2,
                  "over_2_5": pover, "over_1_5": 0.9, "over_3_5": 0.2, "btts_yes": 0.5},
    }


def test_clv_matches_and_counts_unmatched():
    preds = [
        _pred("Inter", "Milan", 2, 0, 0.5, 0.3, 0.2, 0.6),
        _pred("Ghost", "Team", 1, 1, 0.4, 0.3, 0.3, 0.5),
    ]
    odds = index_by_teams([{
        "home": "Inter", "away": "Milan", "fthg": 2, "ftag": 0,
        "o1": 2.2, "ox": 3.4, "o2": 3.3, "oover": 1.9, "ounder": 2.0,
    }])
    rep = evaluate_clv(preds, odds)
    assert rep.matched == 1
    assert rep.unmatched == 1
    assert ("Ghost", "Team") in rep.unmatched_pairs


def test_clv_winning_value_bet_gives_positive_roi():
    # Our model says home 60% at odds 2.2 (implied 45%) -> value; home wins.
    preds = [_pred("Inter", "Milan", 3, 0, 0.60, 0.25, 0.15, 0.55)]
    odds = index_by_teams([{
        "home": "Inter", "away": "Milan", "o1": 2.2, "ox": 3.4, "o2": 3.3,
        "oover": 1.8, "ounder": 2.1,
    }])
    rep = evaluate_clv(preds, odds, edge_threshold=0.0)
    x = next(m for m in rep.markets if m.market == "Risultato 1X2")
    assert x.n_bets >= 1
    assert x.roi > 0            # backed home, it won
    assert x.avg_edge > 0
