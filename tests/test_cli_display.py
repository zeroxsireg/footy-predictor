"""CLI display tests: odds enrichment, quote rendering, categories. No network."""

from datetime import datetime
from types import SimpleNamespace

from cli.betting_render import categorize_market, render_betting_analysis
from cli.player_cards_display import apply_player_odds, render_player_cards
from core.betting_models import BettingRecommendation, MatchBettingAnalysis
from core.daily_models import DailyPick
from core.odds_fetcher import MarketOdds


def _rec(market="Match Goals", selection="Over 2.5", pct=72.0, conf="HIGH"):
    return BettingRecommendation(
        market=market, selection=selection, confidence=conf,
        reasoning="test reasoning", percentage=pct,
    )


def _analysis(recs):
    return SimpleNamespace(
        recommendations=recs, exact_scores=[],
        summary={"total_recommendations": len(recs), "high_confidence": len(recs),
                 "medium_confidence": 0},
    )


def _market_odds(odds=2.10, bookie="Bet365"):
    return MarketOdds(bookmaker_name=bookie, bookmaker_id=8, market="Match Goals",
                      selection="Over 2.5", odds=odds, last_update=datetime(2026, 1, 1))


def test_team_goals_category():
    assert categorize_market("Monza Goals") == "Team Goals"
    assert categorize_market("Match Goals") == "Match Goals"
    assert categorize_market("Total Shots on Goal") == "Total Shots on Goal"
    assert categorize_market("Monza Shots on Goal") == "Team Shots on Goal"
    assert categorize_market("Inter Cards") == "Team Cards"
    assert categorize_market("Total Match Football Goals") == "Team Goals"


def test_render_team_goals_under_team_goals_header(capsys):
    render_betting_analysis(_analysis([_rec("Monza Goals", "Over 1.5"), _rec()]))
    out = capsys.readouterr().out
    team_idx = out.index("Team Goals:")
    assert team_idx < out.index("Monza Goals: Over 1.5")
    assert out.index("Match Goals:") < team_idx


def test_player_pick_with_and_without_odds(capsys):
    pick = DailyPick(match_id=1, home_team="A", away_team="B", market="Player Card - Rico Lewis",
                     selection="Yes", confidence="HIGH", percentage=61.0, reasoning="r",
                     match_time=datetime(2026, 1, 1), league="Serie A", player_team="A")
    nodds = DailyPick(match_id=1, home_team="A", away_team="B", market="Player Card - Bob",
                      selection="Yes", confidence="LOW", percentage=40.0, reasoning="r",
                      match_time=datetime(2026, 1, 1), league="Serie A")
    apply_player_odds([pick, nodds], {"rico lewis": _market_odds(3.0, "Bwin")})
    render_player_cards([pick, nodds])
    out = capsys.readouterr().out
    assert "Quota: 3.00 (Bwin)" in out and "EV:" in out and "Kelly ¼" in out
    assert "quota n/d" in out


def test_player_cards_empty_prints_explicit_line(capsys):
    render_player_cards([])
    assert "nessun dato rosa disponibile" in capsys.readouterr().out
