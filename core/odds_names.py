"""Player-name normalisation and fuzzy matching for bookmaker/roster names.

Bookmakers write "Lautaro Martinez", API-Football rosters write "L. Martinez",
some feeds write "Martinez L." or "Martínez". This module makes them comparable
without ever guessing when the match is ambiguous.
"""

import re
import unicodedata
from typing import Iterable, List, Optional, Tuple

# Letters that NFKD does not decompose into base + combining mark.
_TRANSLITERATION = str.maketrans({
    "ø": "o", "Ø": "O", "ł": "l", "Ł": "L", "đ": "d", "Đ": "D",
    "ħ": "h", "ı": "i", "ð": "d", "þ": "th",
})


def normalize_player_name(name: str) -> str:
    """Lowercase, strip accents/punctuation, collapse spaces ("L. Martínez" -> "l martinez")."""
    if not name:
        return ""
    text = str(name).translate(_TRANSLITERATION)
    text = text.replace("ß", "ss").replace("æ", "ae").replace("Æ", "AE").replace("œ", "oe")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-zA-Z0-9]+", " ", text.lower())
    return " ".join(text.split())


def _parse(normalized: str) -> Tuple[Optional[str], List[str], bool]:
    """Return (initial, surname_tokens, is_abbreviated) for a normalised name.

    Single-letter tokens (in any position) are initials; a name that has one is
    "abbreviated" and its remaining tokens are the surname. For full names the
    initial is the first letter of the first token and the whole token list is
    returned (given names + surname).
    """
    tokens = normalized.split()
    initials = [t for t in tokens if len(t) == 1]
    if initials:
        return initials[0], [t for t in tokens if len(t) > 1], True
    return (tokens[0][0] if tokens else None), tokens, False


def _contains_run(haystack: List[str], needle: List[str]) -> bool:
    n = len(needle)
    return n > 0 and any(haystack[i:i + n] == needle for i in range(len(haystack) - n + 1))


def names_match(a: str, b: str) -> bool:
    """True if two player names plausibly denote the same player."""
    na, nb = normalize_player_name(a), normalize_player_name(b)
    if not na or not nb:
        return False
    if na == nb:
        return True

    ini_a, tok_a, abbr_a = _parse(na)
    ini_b, tok_b, abbr_b = _parse(nb)

    if abbr_a and abbr_b:
        return ini_a == ini_b and tok_a == tok_b
    if abbr_a or abbr_b:
        (ini, surname), full = ((ini_a, tok_a), tok_b) if abbr_a else ((ini_b, tok_b), tok_a)
        if len(full) < 2 or not surname:
            return False
        return full[0][0] == ini and _contains_run(full[1:], surname)
    # Both full names: same first given name and same last token.
    return len(tok_a) > 1 and len(tok_b) > 1 and tok_a[0] == tok_b[0] and tok_a[-1] == tok_b[-1]


def match_player_name(query: str, candidates: Iterable[str]) -> Optional[str]:
    """Return the single candidate matching `query`, or None if none/ambiguous.

    An exact normalised match always wins; otherwise fuzzy matches must be
    unique (two "L. Martinez" candidates -> None rather than a wrong quote).
    """
    candidates = list(candidates)
    nq = normalize_player_name(query)
    if not nq:
        return None
    exact = [c for c in candidates if normalize_player_name(c) == nq]
    if exact:
        return exact[0]
    fuzzy = [c for c in candidates if names_match(query, c)]
    return fuzzy[0] if len(fuzzy) == 1 else None
