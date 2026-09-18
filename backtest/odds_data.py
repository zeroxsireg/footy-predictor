"""
Historical closing odds from football-data.co.uk (free CSV).

API-Football does not expose historical odds, so we use the classic source:
football-data.co.uk publishes per-season CSVs with Bet365 and Pinnacle odds,
both early and CLOSING (the *C columns), for 1X2 and Over/Under 2.5. Closing
Pinnacle is the sharpest line — the hardest, most honest benchmark to beat.

Coverage caveat: Pinnacle closing columns are NOT always populated (2025/26
Serie A: ~50% of matches). Every record therefore carries `source_book` (1X2)
and `source_book_ou` (O/U) naming the book that really supplied the odds, and
the three 1X2 prices always come from the SAME book (never mixed).
"""

import csv
import io
import os
from collections import Counter
from datetime import datetime
from typing import Dict, List, Optional

import httpx

from backtest.data import DATA_DIR

BASE_URL = "https://www.football-data.co.uk/mmz4281"

# football-data team name -> our API-Football name (only the mismatches).
SERIE_A_ALIASES = {
    "Milan": "AC Milan",
    "Roma": "AS Roma",
    "Verona": "Hellas Verona",
    "Parma": "Parma",
}

# football-data name -> API-Football name, only the mismatches (verified against
# backtest/data/odds_*.csv and league_*_season_*.json).
LA_LIGA_ALIASES = {
    "Ath Madrid": "Atletico Madrid",
    "Ath Bilbao": "Athletic Club",
    "Sociedad": "Real Sociedad",
    "Celta": "Celta Vigo",
    "Vallecano": "Rayo Vallecano",
    "Espanol": "Espanyol",
    "Betis": "Real Betis",
    "Granada": "Granada CF",
}
PREMIER_ALIASES = {
    "Man City": "Manchester City",
    "Man United": "Manchester United",
    "Nott'm Forest": "Nottingham Forest",
    "Sheffield United": "Sheffield Utd",
}
LEAGUE_ALIASES = {135: SERIE_A_ALIASES, 140: LA_LIGA_ALIASES, 39: PREMIER_ALIASES}


def season_code(year: int) -> str:
    """2024 -> '2425' (football-data's season folder)."""
    return f"{str(year)[2:]}{str(year + 1)[2:]}"


def csv_cache_path(league_code: str, year: int) -> str:
    return os.path.join(DATA_DIR, f"odds_{league_code}_{year}.csv")


def download_csv(league_code: str, year: int) -> str:
    url = f"{BASE_URL}/{season_code(year)}/{league_code}.csv"
    resp = httpx.get(url, timeout=30, follow_redirects=True)
    resp.raise_for_status()
    return resp.text


def get_csv(league_code: str, year: int, *, refresh: bool = False) -> str:
    path = csv_cache_path(league_code, year)
    if not refresh and os.path.exists(path):
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    text = download_csv(league_code, year)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return text


def _f(row: Dict[str, str], *keys: str) -> Optional[float]:
    """First present, non-empty column among keys, as float."""
    for k in keys:
        v = row.get(k)
        if v not in (None, ""):
            try:
                return float(v)
            except ValueError:
                continue
    return None


# One entry per bookmaker line. "x"/"ou" are the columns of the line itself
# (1X2 home/draw/away, over/under 2.5); "open_x"/"open_ou" are the same book's
# OPENING prices (used for the true CLV: opening price taken vs closing price).
_BOOKS = {
    "pinnacle_close": {"x": ("PSCH", "PSCD", "PSCA"), "ou": ("PC>2.5", "PC<2.5"),
                       "open_x": ("PSH", "PSD", "PSA"), "open_ou": ("P>2.5", "P<2.5")},
    "bet365_close": {"x": ("B365CH", "B365CD", "B365CA"), "ou": ("B365C>2.5", "B365C<2.5"),
                     "open_x": ("B365H", "B365D", "B365A"),
                     "open_ou": ("B365>2.5", "B365<2.5")},
    "avg_close": {"x": ("AvgCH", "AvgCD", "AvgCA"), "ou": ("AvgC>2.5", "AvgC<2.5"),
                  "open_x": ("AvgH", "AvgD", "AvgA"), "open_ou": ("Avg>2.5", "Avg<2.5")},
    "max_close": {"x": ("MaxCH", "MaxCD", "MaxCA"), "ou": ("MaxC>2.5", "MaxC<2.5"),
                  "open_x": ("MaxH", "MaxD", "MaxA"), "open_ou": ("Max>2.5", "Max<2.5")},
    # Opening-only fallbacks (no closing price available: labelled as such).
    "bet365_open": {"x": ("B365H", "B365D", "B365A"), "ou": ("B365>2.5", "B365<2.5")},
    "avg_open": {"x": ("AvgH", "AvgD", "AvgA"), "ou": ("Avg>2.5", "Avg<2.5")},
    "max_open": {"x": ("MaxH", "MaxD", "MaxA"), "ou": ("Max>2.5", "Max<2.5")},
}

# Fallback chain per source. "sharp" = Pinnacle closing first (hardest bar);
# "max" = best available across all books (line-shopping scenario).
_CHAINS = {
    "sharp": ("pinnacle_close", "bet365_close", "avg_close", "bet365_open", "avg_open"),
    "max": ("max_close", "max_open", "pinnacle_close", "bet365_close"),
}


def _complete(row: Dict[str, str], cols) -> Optional[tuple]:
    """All columns present and > 1.0 -> tuple of floats, else None (never partial)."""
    vals = tuple(_f(row, c) for c in cols)
    return vals if all(v is not None and v > 1.0 for v in vals) else None


def _pick_line(row: Dict[str, str], chain, key: str):
    """First book in the chain with a COMPLETE line -> (book, prices, opening prices)."""
    for book in chain:
        cfg = _BOOKS[book]
        prices = _complete(row, cfg[key])
        if prices:
            opening = _complete(row, cfg["open_" + key]) if "open_" + key in cfg else None
            return book, prices, opening
    return None, None, None


def parse_odds(csv_text: str, aliases: Dict[str, str] = None,
               source: str = "sharp") -> List[Dict]:
    """
    Parse a football-data CSV into per-match records with de-aliased team names.

    source="sharp": Pinnacle closing, falling back book-by-book (see _CHAINS).
    source="max":   best available odds across all books (line-shopping).

    Each record reports `source_book` (1X2) / `source_book_ou` (O/U): the book
    that actually supplied ALL prices of that market. `open_*` fields hold the
    same book's opening prices when available (for CLV), else None.
    """
    aliases = aliases or {}
    chain = _CHAINS[source]
    reader = csv.DictReader(io.StringIO(csv_text))
    out = []
    for row in reader:
        home = row.get("HomeTeam")
        away = row.get("AwayTeam")
        if not home or not away:
            continue
        x_book, x, x_open = _pick_line(row, chain, "x")
        ou_book, ou, ou_open = _pick_line(row, chain, "ou")
        x, x_open = x or (None,) * 3, x_open or (None,) * 3
        ou, ou_open = ou or (None,) * 2, ou_open or (None,) * 2
        out.append({
            "date": row.get("Date", ""),
            "home": aliases.get(home, home),
            "away": aliases.get(away, away),
            "fthg": _f(row, "FTHG"),
            "ftag": _f(row, "FTAG"),
            "o1": x[0], "ox": x[1], "o2": x[2],
            "oover": ou[0], "ounder": ou[1],
            "source_book": x_book, "source_book_ou": ou_book,
            "open_o1": x_open[0], "open_ox": x_open[1], "open_o2": x_open[2],
            "open_oover": ou_open[0], "open_ounder": ou_open[1],
        })
    return out


def source_breakdown(records: List[Dict], field: str = "source_book") -> Dict[str, int]:
    """How many records each book supplied (None -> 'nessuna quota')."""
    return dict(Counter(r.get(field) or "nessuna quota" for r in records))


def format_breakdown(records: List[Dict]) -> str:
    """Human-readable 'N Pinnacle / N Bet365 / N altro' line for the CLIs."""
    bd = source_breakdown(records)
    pin = sum(n for b, n in bd.items() if b.startswith("pinnacle"))
    b365 = sum(n for b, n in bd.items() if b.startswith("bet365"))
    other = sum(bd.values()) - pin - b365
    detail = ", ".join(f"{b}={n}" for b, n in sorted(bd.items()))
    return f"{pin} Pinnacle / {b365} Bet365 / {other} altro ({detail})"


def _parse_date(text: str) -> Optional[datetime]:
    """football-data 'dd/mm/yyyy' or 'dd/mm/yy', or ISO 'yyyy-mm-dd[T...]'."""
    text = (text or "").strip()
    for fmt, n in (("%d/%m/%Y", 10), ("%d/%m/%y", 8), ("%Y-%m-%d", 10)):
        try:
            return datetime.strptime(text[:n], fmt)
        except ValueError:
            continue
    return None


def verify_match(fixture: Dict, record: Dict) -> bool:
    """
    Cross-check that an odds record and a fixture/prediction are the SAME match:
    full-time goals must be equal and dates within one day (timezone slack).
    Checks are skipped only for data that is absent on either side.
    """
    fh, fa = fixture.get("home_goals"), fixture.get("away_goals")
    rh, ra = record.get("fthg"), record.get("ftag")
    if None not in (fh, fa, rh, ra) and (int(fh) != int(rh) or int(fa) != int(ra)):
        return False
    d1, d2 = _parse_date(str(fixture.get("date", ""))), _parse_date(record.get("date", ""))
    if d1 and d2 and abs((d1 - d2).days) > 1:
        return False
    return True


def get_serie_a_odds(year: int, *, refresh: bool = False,
                     source: str = "sharp") -> List[Dict]:
    """Serie A (league code I1) odds for a season, de-aliased to our names."""
    text = get_csv("I1", year, refresh=refresh)
    return parse_odds(text, SERIE_A_ALIASES, source=source)


# API-Football league id -> football-data.co.uk league code
LEAGUE_CODES = {135: "I1", 140: "SP1", 39: "E0"}


def get_league_odds(league_id: int, year: int, *, refresh: bool = False,
                    source: str = "sharp") -> List[Dict]:
    """
    Odds for any supported league, team names de-aliased through the explicit
    per-league table (LEAGUE_ALIASES). Unknown names stay raw and are handled
    (and verified against goals/date) by the bankroll layer.
    """
    code = LEAGUE_CODES[league_id]
    text = get_csv(code, year, refresh=refresh)
    return parse_odds(text, aliases=LEAGUE_ALIASES.get(league_id, {}), source=source)


def index_by_teams(records: List[Dict]) -> Dict[tuple, Dict]:
    """Index odds by (home, away) — a unique ordered pairing per season."""
    return {(r["home"], r["away"]): r for r in records}
