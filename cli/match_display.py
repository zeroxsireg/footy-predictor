"""
Match display module — all terminal rendering for match analysis.

Responsible for: printing match stats, betting recommendations,
player cards picks, exact scores, and betting summary.
No routing, no business logic, no API calls.
"""

import asyncio
import logging

import httpx

from cli.betting_render import render_betting_analysis, _render_rec  # noqa: F401 (re-export)
from cli.player_cards_display import display_player_cards_picks as _display_player_cards

logger = logging.getLogger(__name__)


# ── match header + stats ──────────────────────────────────────────────────────

async def display_matchday(predictions, league_id=None, season=None, round_number=None):
    """Render the full matchday analysis including betting and player picks."""
    if not predictions:
        print("⚠️ Nessuna partita trovata.")
        return

    from analyzers.player_cards_analyzer import PlayerCardsAnalyzer
    from adapters.football_api import FootballAPIClient

    player_card_analyzer = PlayerCardsAnalyzer()
    api_client = FootballAPIClient()

    round_text = f" - Giornata {round_number}" if round_number else ""
    print(f"\n🏆 ANALISI PARTITE{round_text}")
    print("═" * 60)

    for i, prediction in enumerate(predictions, 1):
        fixture = prediction.fixture

        print(f"\n┌─ MATCH {i} " + "─" * 45)
        print(f"│ 🏠 {fixture.home_team.name:<25} vs ✈️  {fixture.away_team.name}")

        day_name_it = {
            "Monday": "Lunedì", "Tuesday": "Martedì", "Wednesday": "Mercoledì",
            "Thursday": "Giovedì", "Friday": "Venerdì",
            "Saturday": "Sabato", "Sunday": "Domenica",
        }.get(fixture.date.strftime("%A"), fixture.date.strftime("%A"))
        print(f"│ 📅 {fixture.date.strftime('%d/%m/%Y')} • {day_name_it} • {fixture.date.strftime('%H:%M')}")
        if fixture.venue:
            print(f"│ 🏟️  {fixture.venue}")
        print("└" + "─" * 52)

        if prediction.status == "TO AVOID":
            print("\n┌─ ⚠️  MATCH TO AVOID " + "─" * 28)
            print(f"│ 🚫 {prediction.warning}")
            print(f"│ 📊 Squadre non tracciabili: {', '.join(prediction.untracked_teams)}")
            print("│ ❌ Match escluso dall'analisi per dati insufficienti")
            print("│ 💡 Raccomandazione: Evitare per scommesse/analisi")
            print("└" + "─" * 52)
            continue

        _print_team_stats(prediction.home_stats, prediction.away_stats)

        print("\n┌─ 🔮 PREVISIONI MATCH " + "─" * 27)
        print(f"│ ⚽ Gol Totali Attesi:      {prediction.expected_total_goals:.1f}")
        if prediction.expected_total_corners > 0:
            print(f"│ 📐 Corner Totali Attesi:   {prediction.expected_total_corners:.1f}")
        print(f"│ 🟨 Cartellini Attesi:     {prediction.expected_total_yellow_cards:.1f}")
        if prediction.expected_total_corners == 0:
            print("│ 📝 Corner: Dati limitati, calcolo approssimativo")
        print("└" + "─" * 52)

        await display_betting_predictions(prediction, league_id, season)
        await display_player_cards_picks(
            fixture, prediction, player_card_analyzer, api_client,
            league_id, season, league_name="Serie A"
        )

        if i < len(predictions):
            print("\n" + "═" * 60)


def _print_team_stats(home_stats, away_stats):
    """Print the full two-column stats table for home vs away."""
    print("\n┌─ 📊 STATISTICHE SQUADRE " + "─" * 25)
    print("│")

    def section(title, rows):
        print(f"│ {title}")
        print("│ " + "─" * 50)
        for label, hv, av in rows:
            print(f"│ {label:<22} {hv:<12} {av:<12}")
        print("│")

    section("📈 STATISTICHE GENERALI", [
        ("⚽ Partite Giocate", str(home_stats.matches_played), str(away_stats.matches_played)),
        ("🎯 Gol Fatti/Subiti",
         f"{home_stats.goals_for}/{home_stats.goals_against}",
         f"{away_stats.goals_for}/{away_stats.goals_against}"),
        ("📈 Gol per Partita",
         f"{home_stats.goals_per_game:.2f}", f"{away_stats.goals_per_game:.2f}"),
        ("📉 Gol Subiti/Partita",
         f"{home_stats.goals_conceded_per_game:.2f}",
         f"{away_stats.goals_conceded_per_game:.2f}"),
        ("🏆 Vittorie-Pareggi-Sconfitte",
         f"{home_stats.wins}-{home_stats.draws}-{home_stats.losses}",
         f"{away_stats.wins}-{away_stats.draws}-{away_stats.losses}"),
    ])
    section("🔥 FORMA E RENDIMENTO", [
        ("📊 Forma Recente (10)",
         home_stats.form[-10:] if home_stats.form else "N/A",
         away_stats.form[-10:] if away_stats.form else "N/A"),
        ("⭐ Punti Forma (5)",
         str(home_stats.recent_form_points), str(away_stats.recent_form_points)),
        ("🛡️  Porte Inviolate",
         f"{home_stats.clean_sheets} ({home_stats.clean_sheet_percentage:.1f}%)",
         f"{away_stats.clean_sheets} ({away_stats.clean_sheet_percentage:.1f}%)"),
        ("🚫 Senza Segnare",
         f"{home_stats.failed_to_score} ({home_stats.failed_to_score_percentage:.1f}%)",
         f"{away_stats.failed_to_score} ({away_stats.failed_to_score_percentage:.1f}%)"),
    ])
    section("⚡ STATISTICHE AVANZATE", [
        ("🥅 Rigori (Seg/Tot)",
         f"{home_stats.penalties_scored}/{home_stats.penalties_scored + home_stats.penalties_missed}",
         f"{away_stats.penalties_scored}/{away_stats.penalties_scored + away_stats.penalties_missed}"),
        ("🎯 % Rigori",
         f"{home_stats.penalty_conversion_rate:.1f}%",
         f"{away_stats.penalty_conversion_rate:.1f}%"),
        ("🟨 Cartellini Gialli",
         f"{home_stats.yellow_cards} ({home_stats.yellow_cards_per_game:.2f}/p)",
         f"{away_stats.yellow_cards} ({away_stats.yellow_cards_per_game:.2f}/p)"),
        ("🟥 Cartellini Rossi", str(home_stats.red_cards), str(away_stats.red_cards)),
    ])
    section("🎯 STATISTICHE GOL", [
        ("📊 Over 1.5 Gol",
         f"{home_stats.over_1_5_goals_percentage:.1f}%",
         f"{away_stats.over_1_5_goals_percentage:.1f}%"),
        ("📊 Over 2.5 Gol",
         f"{home_stats.over_2_5_goals_percentage:.1f}%",
         f"{away_stats.over_2_5_goals_percentage:.1f}%"),
        ("📊 Over 3.5 Gol",
         f"{home_stats.over_3_5_goals_percentage:.1f}%",
         f"{away_stats.over_3_5_goals_percentage:.1f}%"),
    ])
    section("🏹 TIRI E CORNER", [
        ("🏹 Tiri Totali",
         f"{home_stats.shots_total} ({home_stats.shots_per_game:.1f}/p)",
         f"{away_stats.shots_total} ({away_stats.shots_per_game:.1f}/p)"),
        ("🎯 Tiri in Porta",
         f"{home_stats.shots_on_target} ({home_stats.shots_on_target_per_game:.1f}/p)",
         f"{away_stats.shots_on_target} ({away_stats.shots_on_target_per_game:.1f}/p)"),
        ("📐 Corner",
         f"{home_stats.corners} ({home_stats.corners_per_game:.1f}/p)",
         f"{away_stats.corners} ({away_stats.corners_per_game:.1f}/p)"),
    ])
    print("└" + "─" * 52)


# ── betting predictions ───────────────────────────────────────────────────────

def _apply_market_odds(rec, market_odds) -> bool:
    """Attach a MarketOdds (dataclass) to a recommendation and compute edge/EV/Kelly."""
    from core.edge_calculator import evaluate_bet

    odds = getattr(market_odds, "odds", None)
    if not odds:
        return False
    rec.real_odds = odds
    rec.bookmaker = getattr(market_odds, "bookmaker_name", None) or "N/A"
    decision = evaluate_bet(rec.percentage, rec.real_odds)
    rec.edge = decision.edge
    rec.ev_percent = decision.ev_percent
    rec.kelly_quarter = decision.kelly_quarter
    rec.verdict = decision.verdict
    return True


async def display_betting_predictions(prediction, league_id=None, season=None):
    """Orchestrate betting analysis + odds enrichment, then render."""
    from betting.orchestrator import BettingOrchestrator
    from core.odds_fetcher import OddsFetcher
    if not prediction.home_stats or not prediction.away_stats:
        print("⚠️  Statistiche non disponibili per questa partita")
        return None

    orchestrator = BettingOrchestrator()
    analysis = orchestrator.analyze_match(prediction.home_stats, prediction.away_stats)

    odds_fetcher = OddsFetcher()
    await odds_fetcher.initialize()

    fixture_id = getattr(getattr(prediction, "fixture", None), "id", None)
    if fixture_id:
        for rec in analysis.recommendations:
            try:
                result = await odds_fetcher.get_odds_for_market(
                    fixture_id=fixture_id, market=rec.market, selection=rec.selection
                )
            except (httpx.HTTPError, asyncio.TimeoutError, ConnectionError, OSError) as exc:
                logger.warning("Odds unavailable for %s %s: %s", rec.market, rec.selection, exc)
                continue
            _apply_market_odds(rec, result)

    render_betting_analysis(analysis)
    return analysis


# ── player cards (moved to cli/player_cards_display.py) ──────────────────────

async def display_player_cards_picks(*args, **kwargs):
    """Backward-compatible wrapper around cli.player_cards_display."""
    return await _display_player_cards(*args, **kwargs)


# ── player predictions (legacy) ───────────────────────────────────────────────

def render_player_predictions(player_predictions):
    """Render legacy player card predictions from a PlayerPredictions object."""
    print("\n🟨 PLAYER CARD PREDICTIONS")
    print("=" * 50)

    pos_emoji = {"defender": "🛡️", "midfielder": "⚽", "forward": "🎯", "goalkeeper": "🥅"}

    def _print_group(title, preds):
        print(f"\n{title}")
        print("─" * 45)
        for i, pred in enumerate(preds[:3], 1):
            conf_emoji = {"HIGH": "🔥", "MEDIUM": "⚡", "LOW": "💫"}.get(pred.confidence, "")
            conf_color = {"HIGH": "🟥", "MEDIUM": "🟨", "LOW": "🟦"}.get(pred.confidence, "")
            pe = pos_emoji.get(pred.player.position.lower(), "👤")
            print(f"{i}. {pe} {pred.player.name}")
            print(f"   {conf_emoji} {conf_color} {pred.confidence} │ 📊 {pred.percentage:.1f}% │ 💰 {pred.estimated_odds}")
            print(f"   💬 {pred.reasoning}")
            print()

    _print_group(
        f"🏠 {player_predictions.fixture.home_team.name.upper()} - TOP 3 PLAYERS:",
        player_predictions.home_predictions,
    )
    _print_group(
        f"✈️ {player_predictions.fixture.away_team.name.upper()} - TOP 3 PLAYERS:",
        player_predictions.away_predictions,
    )

    all_preds = player_predictions.home_predictions + player_predictions.away_predictions
    high = sorted([p for p in all_preds if p.confidence == "HIGH"], key=lambda x: -x.percentage)
    if high:
        print("🎯 OVERALL HIGH CONFIDENCE PICKS:")
        print("─" * 40)
        print("📈 Ordered by probability (highest first)")
        print()
        for i, pred in enumerate(high, 1):
            home_id = player_predictions.fixture.home_team.id
            is_home = pred.player.team_id == home_id
            team_emoji = "🏠" if is_home else "✈️"
            team_name = (
                player_predictions.fixture.home_team.name
                if is_home
                else player_predictions.fixture.away_team.name
            )
            pe = pos_emoji.get(pred.player.position.lower(), "👤")
            pct_emoji = (
                "🔴" if pred.percentage >= 80 else
                "🟠" if pred.percentage >= 60 else
                "🟡" if pred.percentage >= 40 else "🟢"
            )
            print(f"{i}. {team_emoji} {pe} {pred.player.name} ({team_name})")
            print(f"   {pct_emoji} {pred.percentage:.1f}% │ 💰 {pred.estimated_odds} │ 🔥 {pred.confidence}")
        print()
