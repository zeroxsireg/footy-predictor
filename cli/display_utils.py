"""
Display utilities for unified emoji and formatting across all modules.
"""

def get_confidence_emoji(confidence: str) -> str:
    """Get emoji for confidence level."""
    emoji_map = {
        "HIGH": "🔥",
        "MEDIUM": "⚡",
        "LOW": "⚠️"
    }
    return emoji_map.get(confidence.upper(), "📊")


def get_probability_emoji(percentage: float) -> str:
    """Get emoji for probability percentage."""
    if percentage >= 75:
        return "✅"  # Altissima
    elif percentage >= 60:
        return "📊"  # Alta
    else:
        return "❗"  # Media/Bassa


def get_odds_display(real_odds: float = None, bookmaker: str = None, percentage: float = 0) -> str:
    """Get formatted odds display string."""
    prob_emoji = get_probability_emoji(percentage)
    
    if real_odds and bookmaker:
        return f"💎 Quota: {real_odds:.2f} ({bookmaker}) • {prob_emoji} {percentage:.1f}%"
    else:
        return f"{prob_emoji} {percentage:.1f}% • ❌ Quote non disponibili"


def format_pick_display(pick_number: int, confidence: str, market: str, selection: str, 
                        real_odds: float = None, bookmaker: str = None, 
                        percentage: float = 0, reasoning: str = "") -> str:
    """Format a complete pick display."""
    conf_emoji = get_confidence_emoji(confidence)
    odds_line = get_odds_display(real_odds, bookmaker, percentage)
    
    lines = [
        f"   Pick {pick_number}: {conf_emoji} {market}: {selection}",
        f"           {odds_line}",
        f"           💬 {reasoning}"
    ]
    
    return "\n".join(lines)

