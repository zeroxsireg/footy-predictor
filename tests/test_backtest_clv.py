"""Tests for odds parsing and CLV evaluation."""

import pytest

from backtest.odds_data import (parse_odds, index_by_teams, season_code, SERIE_A_ALIASES,
                                LEAGUE_ALIASES, format_breakdown, verify_match)
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
    assert r["source_book"] == "bet365_close"


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
    rep = evaluate_clv(preds, odds, ev_threshold=0.0)
    x = next(m for m in rep.markets if m.market == "Risultato 1X2")
    assert x.n_bets >= 1
    assert x.roi_close > 0            # backed home, it won
    assert x.avg_edge > 0


# ── source book traceability (B) ─────────────────────────────────────────────

def test_parse_odds_never_mixes_books_within_1x2():
    # Pinnacle has home+draw but NO away price: the whole line must come from Bet365.
    csv_text = (
        "Date,HomeTeam,AwayTeam,FTHG,FTAG,PSCH,PSCD,PSCA,B365CH,B365CD,B365CA\n"
        "18/08/2025,Inter,Lecce,3,0,1.30,5.0,,1.28,5.2,9.5\n"
    )
    r = parse_odds(csv_text)[0]
    assert r["source_book"] == "bet365_close"
    assert (r["o1"], r["ox"], r["o2"]) == (1.28, 5.2, 9.5)


def test_parse_odds_reports_pinnacle_and_opening_prices():
    csv_text = (
        "Date,HomeTeam,AwayTeam,FTHG,FTAG,PSH,PSD,PSA,PSCH,PSCD,PSCA\n"
        "18/08/2025,Inter,Lecce,3,0,1.40,4.8,8.0,1.30,5.0,9.0\n"
    )
    r = parse_odds(csv_text)[0]
    assert r["source_book"] == "pinnacle_close"
    assert r["open_o1"] == 1.40 and r["o1"] == 1.30


def test_parse_odds_labels_opening_only_fallback():
    csv_text = "Date,HomeTeam,AwayTeam,B365H,B365D,B365A\n18/08/2025,A,B,2.0,3.0,4.0\n"
    r = parse_odds(csv_text)[0]
    assert r["source_book"] == "bet365_open"
    assert r["open_o1"] is None      # no closing price -> no CLV possible


def test_format_breakdown_counts_books():
    recs = [{"source_book": "pinnacle_close"}, {"source_book": "bet365_close"},
            {"source_book": "bet365_close"}, {"source_book": "avg_close"}]
    txt = format_breakdown(recs)
    assert txt.startswith("1 Pinnacle / 2 Bet365 / 1 altro")


def test_la_liga_and_premier_aliases_cover_known_mismatches():
    assert LEAGUE_ALIASES[140]["Ath Madrid"] == "Atletico Madrid"
    assert LEAGUE_ALIASES[140]["Ath Bilbao"] == "Athletic Club"
    assert LEAGUE_ALIASES[39]["Man City"] == "Manchester City"
    assert LEAGUE_ALIASES[39]["Nott'm Forest"] == "Nottingham Forest"


def test_verify_match_goals_and_date():
    rec = {"fthg": 2.0, "ftag": 1.0, "date": "15/08/2025"}
    ok = {"home_goals": 2, "away_goals": 1, "date": "2025-08-15T17:00:00+00:00"}
    assert verify_match(ok, rec)
    assert not verify_match({**ok, "home_goals": 3}, rec)
    assert not verify_match({**ok, "date": "2025-09-20T17:00:00+00:00"}, rec)


# ── true CLV (C) ─────────────────────────────────────────────────────────────

def test_clv_measures_open_vs_close_same_book():
    preds = [_pred("Inter", "Milan", 1, 0, 0.60, 0.25, 0.15, 0.5)]
    odds = index_by_teams([{
        "home": "Inter", "away": "Milan", "o1": 2.0, "ox": 3.5, "o2": 4.0,
        "open_o1": 2.4, "open_ox": 3.4, "open_o2": 3.8,
    }])
    x = next(m for m in evaluate_clv(preds, odds, ev_threshold=0.03).markets
             if m.market == "Risultato 1X2")
    fair_home = _devig(2.0, 3.5, 4.0)[0]
    assert x.n_clv_bets == 1                       # only the home selection has EV > 3%
    assert x.clv_odds == pytest.approx(2.4 / 2.0 - 1, abs=1e-4)
    assert x.clv_fair == pytest.approx(fair_home * 2.4 - 1, abs=1e-4)


def test_clv_absent_without_opening_prices():
    preds = [_pred("Inter", "Milan", 1, 0, 0.60, 0.25, 0.15, 0.5)]
    odds = index_by_teams([{"home": "Inter", "away": "Milan",
                            "o1": 2.0, "ox": 3.5, "o2": 4.0}])
    x = evaluate_clv(preds, odds, ev_threshold=0.03).markets[0]
    assert x.clv_odds is None and x.n_clv_bets == 0


def test_evaluate_clv_rejects_incoherent_goals():
    preds = [_pred("Inter", "Milan", 2, 0, 0.5, 0.3, 0.2, 0.6)]
    odds = index_by_teams([{"home": "Inter", "away": "Milan", "fthg": 0, "ftag": 3,
                            "o1": 2.2, "ox": 3.4, "o2": 3.3}])
    rep = evaluate_clv(preds, odds)
    assert rep.matched == 0 and rep.unmatched == 1
    assert rep.rejected_pairs == [("Inter", "Milan")]


def test_clv_uses_ev_rule_not_raw_edge():
    # p=0.23 at odds 5.0: EV=+15% but raw edge only +3%. Threshold 5% -> must bet.
    preds = [_pred("A", "B", 0, 0, 0.23, 0.40, 0.37, 0.5)]
    odds = index_by_teams([{"home": "A", "away": "B", "o1": 5.0, "ox": 2.0, "o2": 2.0}])
    x = evaluate_clv(preds, odds, ev_threshold=0.05).markets[0]
    assert x.n_bets == 1
