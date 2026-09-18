"""
Betting render module — terminal rendering of betting recommendations.

Pure presentation: categorizes recommendations and prints them with real
odds, bookmaker, edge, EV and Quarter Kelly when available.
No API calls, no odds logic.
"""

from typing import Any, Dict, List, Optional

# Exact market names first, then team-market suffixes ("<Team> Goals", ...).
_EXACT_CATEGORIES = {
    "Match Goals": "Match Goals",
    "Both Teams to Score": "Both Teams to Score",
    "Match Result": "Match Result",
    "Total Shots on Goal": "Total Shots on Goal",
    "Total Shots": "Total Shots",
    "Total Corners": "Total Corners",
    "Total Cards": "Total Cards",
}
# Longest suffix first: " Shots on Goal" must win over " Goals"/" Shots".
_SUFFIX_CATEGORIES = [
    (" Shots on Goal", "Team Shots on Goal"),
    (" Shots", "Team Shots"),
    (" Goals", "Team Goals"),
    (" Corners", "Team Corners"),
    (" Cards", "Team Cards"),
]

_ICONS = {
    "Match Goals": "⚽", "Team Goals": "🎯", "Both Teams to Score": "🤝",
    "Total Shots": "🏹", "Total Shots on Goal": "🎯",
    "Team Shots": "🏹", "Team Shots on Goal": "🎯",
    "Total Corners": "📐", "Team Corners": "🚩",
    "Total Cards": "🟨", "Team Cards": "🟥", "Match Result": "🏆",
}
_SECTIONS = {
    "⚽ GOL E RISULTATO": ["Match Goals", "Team Goals", "Both Teams to Score", "Match Result"],
    "🏹 TIRI": ["Total Shots", "Total Shots on Goal", "Team Shots", "Team Shots on Goal"],
    "📐 CORNER": ["Total Corners", "Team Corners"],
    "🟨 CARTELLINI": ["Total Cards", "Team Cards"],
}


def categorize_market(market: str) -> Optional[str]:
    """Map a market name to its render category (None if unknown)."""
    if market in _EXACT_CATEGORIES:
        return _EXACT_CATEGORIES[market]
    for suffix, category in _SUFFIX_CATEGORIES:
        if market.endswith(suffix):
            return category
    return None


def categorize_recommendations(recommendations) -> Dict[str, List[Any]]:
    """Group recommendations by render category."""
    categories: Dict[str, List[Any]] = {c: [] for c in _ICONS}
    for rec in recommendations:
        category = categorize_market(rec.market or "")
        if category:
            categories[category].append(rec)
    return categories


def format_quote_lines(item: Any, prob_emoji: str = "📊") -> List[str]:
    """
    Build the quote/edge lines for a recommendation or a player pick.

    Works with any object exposing (optionally) real_odds, bookmaker, edge,
    ev_percent, kelly_quarter, verdict, percentage. Missing/None values never raise.
    """
    odds = getattr(item, "real_odds", None)
    bookmaker = getattr(item, "bookmaker", None) or "N/A"
    pct = getattr(item, "percentage", None)
    pct_txt = f"{pct:.1f}%" if isinstance(pct, (int, float)) else "N/A"

    if not odds:
        return [f"{prob_emoji} {pct_txt} • ⚪ quota n/d"]

    lines = [f"💎 Quota: {odds:.2f} ({bookmaker}) • {prob_emoji} {pct_txt}"]
    edge = getattr(item, "edge", None)
    ev = getattr(item, "ev_percent", None)
    kelly = getattr(item, "kelly_quarter", None)
    if edge is None and ev is None and kelly is None:
        return lines
    verdict = getattr(item, "verdict", None) or "N/A"
    verdict_emoji = "✅" if verdict == "BET" else "⚡" if verdict == "VALUE" else "❌"
    parts = []
    if edge is not None:
        parts.append(f"Edge: {'+' if edge >= 0 else ''}{edge * 100:.1f}%")
    if ev is not None:
        parts.append(f"EV: {'+' if ev >= 0 else ''}{ev:.1f}%")
    if kelly is not None:
        parts.append(f"Kelly ¼: {kelly * 100:.1f}% bankroll")
    lines.append(f"📈 {' • '.join(parts)}  {verdict_emoji} {verdict}")
    return lines


def _render_rec(rec, confidence_emoji: str):
    pct = rec.percentage or 0.0
    prob_emoji = "✅" if pct >= 75 else "📊" if pct >= 60 else "❗"
    print(f"│   {confidence_emoji} {rec.market}: {rec.selection}")
    for line in format_quote_lines(rec, prob_emoji):
        print(f"│      {line}")
    print(f"│      💬 {rec.reasoning}")
    print("│")


def render_betting_analysis(analysis):
    """Render a MatchBettingAnalysis to stdout."""
    if not analysis.recommendations:
        return

    categories = categorize_recommendations(analysis.recommendations)

    print("\n┌─ 🎯 RACCOMANDAZIONI SCOMMESSE " + "─" * 20)
    print("│")

    for section_name, section_cats in _SECTIONS.items():
        if not any(categories.get(c) for c in section_cats):
            continue
        print("│")
        print(f"│ {'═' * 50}")
        print(f"│ {section_name}")
        print(f"│ {'═' * 50}")

        for cat in section_cats:
            recs = categories.get(cat, [])
            if not recs:
                continue
            print("│")
            print(f"│ {_ICONS[cat]} {cat}:")
            print(f"│ {'─' * 48}")
            for rec in [r for r in recs if r.confidence == "HIGH"]:
                _render_rec(rec, "🔥")
            for rec in [r for r in recs if r.confidence == "MEDIUM"]:
                _render_rec(rec, "⚡")

    print("└" + "─" * 52)

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

    print("📋 BETTING SUMMARY:")
    print("-" * 20)
    s = analysis.summary
    print(f"Total Recommendations: {s['total_recommendations']}")
    print(f"High Confidence:       {s['high_confidence']}")
    print(f"Medium Confidence:     {s['medium_confidence']}")
    print(f"🎯 Most Likely Score: {s.get('most_likely_score', 'N/A')}")
    print(f"🏆 Top Pick:          {s.get('top_pick', 'N/A')}")
