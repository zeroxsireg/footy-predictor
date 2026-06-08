"""
Match display module — all terminal rendering for match analysis.

Responsible for: printing match stats, betting recommendations,
player cards picks, exact scores, and betting summary.
No routing, no business logic, no API calls.
"""

from typing import List, Optional


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

async def display_betting_predictions(prediction, league_id=None, season=None):
    """Orchestrate betting analysis + odds enrichment, then render."""
    from betting.orchestrator import BettingOrchestrator
    from core.odds_fetcher import OddsFetcher
    from core.edge_calculator import evaluate_bet

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
                if result and result.get("odds"):
                    rec.real_odds = result["odds"]
                    rec.bookmaker = result.get("bookmaker", "N/A")
                    decision = evaluate_bet(rec.percentage, rec.real_odds)
                    rec.edge = decision.edge
                    rec.ev_percent = decision.ev_percent
                    rec.kelly_quarter = decision.kelly_quarter
                    rec.verdict = decision.verdict
            except Exception:
                pass

    render_betting_analysis(analysis)
    return analysis


def render_betting_analysis(analysis):
    """Render a MatchBettingAnalysis to stdout."""
    if not analysis.recommendations:
        return

    # Category mapping
    categories = {
        "Match Goals": [], "Team Goals": [], "Both Teams to Score": [],
        "Total Shots": [], "Total Shots on Goal": [],
        "Team Shots": [], "Team Shots on Goal": [],
        "Total Corners": [], "Team Corners": [],
        "Total Cards": [], "Team Cards": [], "Match Result": [],
    }

    for rec in analysis.recommendations:
        m = rec.market
        if "Match Goals" in m:
            categories["Match Goals"].append(rec)
        elif "Both Teams to Score" in m:
            categories["Both Teams to Score"].append(rec)
        elif "Goals" in m and "Total" not in m and "Match" not in m:
            categories["Team Goals"].append(rec)
        elif "Goals" in m:
            categories["Match Goals"].append(rec)
        elif "Total Shots on Goal" in m:
            categories["Total Shots on Goal"].append(rec)
        elif "Total Shots" in m:
            categories["Total Shots"].append(rec)
        elif "Shots on Goal" in m:
            categories["Team Shots on Goal"].append(rec)
        elif "Shots" in m:
            categories["Team Shots"].append(rec)
        elif "Total Corners" in m:
            categories["Total Corners"].append(rec)
        elif "Corners" in m:
            categories["Team Corners"].append(rec)
        elif "Total Cards" in m:
            categories["Total Cards"].append(rec)
        elif "Cards" in m:
            categories["Team Cards"].append(rec)
        elif "Match Result" in m:
            categories["Match Result"].append(rec)

    icons = {
        "Match Goals": "⚽", "Team Goals": "🎯", "Both Teams to Score": "🤝",
        "Total Shots": "🏹", "Total Shots on Goal": "🎯",
        "Team Shots": "🏹", "Team Shots on Goal": "🎯",
        "Total Corners": "📐", "Team Corners": "🚩",
        "Total Cards": "🟨", "Team Cards": "🟥", "Match Result": "🏆",
    }
    sections = {
        "⚽ GOL E RISULTATO": ["Match Goals", "Team Goals", "Both Teams to Score", "Match Result"],
        "🏹 TIRI": ["Total Shots", "Total Shots on Goal", "Team Shots", "Team Shots on Goal"],
        "📐 CORNER": ["Total Corners", "Team Corners"],
        "🟨 CARTELLINI": ["Total Cards", "Team Cards"],
    }

    print("\n┌─ 🎯 RACCOMANDAZIONI SCOMMESSE " + "─" * 20)
    print("│")

    for section_name, section_cats in sections.items():
        if not any(categories.get(c) for c in section_cats):
            continue
        print(f"│")
        print(f"│ {'═' * 50}")
        print(f"│ {section_name}")
        print(f"│ {'═' * 50}")

        for cat in section_cats:
            recs = categories.get(cat, [])
            if not recs:
                continue
            print(f"│")
            print(f"│ {icons[cat]} {cat}:")
            print(f"│ {'─' * 48}")
            high = [r for r in recs if r.confidence == "HIGH"]
            medium = [r for r in recs if r.confidence == "MEDIUM"]
            for rec in high:
                _render_rec(rec, "🔥")
            for rec in medium:
                _render_rec(rec, "⚡")

    print("└" + "─" * 52)

    # Exact scores
    if getattr(analysis, "exact_scores", None):
        print("\n⚽ EXACT SCORE PREDICTIONS:")
        print("═" * 40)
        for i, sp in enumerate(analysis.exact_scores[:2], 1):
            h, a = sp.score.split("-")
            result_emoji = "🏠" if int(h) > int(a) else "✈️" if int(h) < int(a) else "🤝"
            prob_color = "🔴" if sp.probability >= 15 else "🟠" if sp.probability >= 10 else "🟡"
            print(f"{i}. {result_emoji} {sp.score}")
            print(f"   {prob_color} Probability: {sp.probability:.1f}% │ 💰 Odds: {sp.odds_estimate}")
            print(f"   💬 {sp.reasoning}")
            print()

    # Summary
    print("📋 BETTING SUMMARY:")
    print("-" * 20)
    s = analysis.summary
    print(f"Total Recommendations: {s['total_recommendations']}")
    print(f"High Confidence:       {s['high_confidence']}")
    print(f"Medium Confidence:     {s['medium_confidence']}")
    print(f"🎯 Most Likely Score: {s.get('most_likely_score', 'N/A')}")
    print(f"🏆 Top Pick:          {s.get('top_pick', 'N/A')}")


def _render_rec(rec, confidence_emoji: str):
    prob_emoji = "✅" if rec.percentage >= 75 else "📊" if rec.percentage >= 60 else "❗"
    print(f"│   {confidence_emoji} {rec.market}: {rec.selection}")
    if rec.real_odds and rec.bookmaker:
        print(f"│      💎 Quota: {rec.real_odds:.2f} ({rec.bookmaker}) • {prob_emoji} {rec.percentage:.1f}%")
        if rec.edge is not None:
            edge_sign = "+" if rec.edge >= 0 else ""
            verdict_emoji = "✅" if rec.verdict == "BET" else "⚡" if rec.verdict == "VALUE" else "❌"
            kelly_pct = (rec.kelly_quarter or 0) * 100
            print(
                f"│      📈 Edge: {edge_sign}{rec.edge*100:.1f}%"
                f" • EV: {'+' if (rec.ev_percent or 0) >= 0 else ''}{rec.ev_percent:.1f}%"
                f" • Kelly ¼: {kelly_pct:.1f}% bankroll"
                f"  {verdict_emoji} {rec.verdict}"
            )
    else:
        print(f"│      {prob_emoji} {rec.percentage:.1f}% • ❌ Quote non disponibili")
    print(f"│      💬 {rec.reasoning}")
    print("│")


# ── player cards ──────────────────────────────────────────────────────────────

async def display_player_cards_picks(
    fixture, prediction, player_card_analyzer, api_client,
    league_id, season, league_name="Unknown League"
):
    """Display top player cards picks for a match."""
    try:
        from analyzers.player_cards_analyzer import PlayerCardsAnalyzer
        analyzer = PlayerCardsAnalyzer()
        picks = await analyzer.analyze_match_players(fixture, [], league_name, api_client)
        if not picks:
            return

        top_picks = picks[:5]
        if not top_picks:
            return

        print(f"\n🟨 TOP {len(top_picks)} GIOCATORI A RISCHIO AMMONIZIONE:")
        print("═" * 60)

        for i, pick in enumerate(top_picks, 1):
            conf_emoji = "🔥" if pick.confidence == "HIGH" else "⚡" if pick.confidence == "MEDIUM" else "💡"
            player_name = pick.market.replace("Player Card - ", "")
            team_name = pick.player_team if pick.player_team else ""
            pct_color = "🔴" if pick.percentage >= 75 else "🟠" if pick.percentage >= 60 else "🟡"
            print(f" {i}. {conf_emoji} {player_name}")
            if team_name:
                print(f"    🏟️  {team_name}")
            print(f"    💰 {pick.odds_range} • {pct_color} {pick.percentage:.1f}%")
            print(f"    💬 {pick.reasoning}")
            print()

        print("─" * 60)

    except Exception as exc:
        print(f"⚠️  Player cards analysis unavailable: {exc}")


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
