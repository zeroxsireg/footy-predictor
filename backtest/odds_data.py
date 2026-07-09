"""
Historical closing odds from football-data.co.uk (free CSV).

API-Football does not expose historical odds, so we use the classic source:
football-data.co.uk publishes per-season CSVs with Bet365 and Pinnacle odds,
both early and CLOSING (the *C columns), for 1X2 and Over/Under 2.5. Closing
Pinnacle is the sharpest line — the hardest, most honest benchmark to beat.
"""

import csv
import io
import os
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


# Column priority per odds source. "sharp" = Pinnacle closing (hardest bar);
# "max" = best available across all books at closing (the line-shopping scenario).
_COLUMNS = {
    "sharp": {
        "o1": ("PSCH", "B365CH", "B365H", "AvgCH", "AvgH"),
        "ox": ("PSCD", "B365CD", "B365D", "AvgCD", "AvgD"),
        "o2": ("PSCA", "B365CA", "B365A", "AvgCA", "AvgA"),
        "oover": ("PC>2.5", "B365C>2.5", "B365>2.5", "AvgC>2.5", "Avg>2.5"),
        "ounder": ("PC<2.5", "B365C<2.5", "B365<2.5", "AvgC<2.5", "Avg<2.5"),
    },
    "max": {
        "o1": ("MaxCH", "MaxH", "PSCH", "B365CH"),
        "ox": ("MaxCD", "MaxD", "PSCD", "B365CD"),
        "o2": ("MaxCA", "MaxA", "PSCA", "B365CA"),
        "oover": ("MaxC>2.5", "Max>2.5", "PC>2.5", "B365C>2.5"),
        "ounder": ("MaxC<2.5", "Max<2.5", "PC<2.5", "B365C<2.5"),
    },
}


def parse_odds(csv_text: str, aliases: Dict[str, str] = None,
               source: str = "sharp") -> List[Dict]:
    """
    Parse a football-data CSV into per-match records with de-aliased team names.

    source="sharp": Pinnacle closing (hardest line to beat).
    source="max":   best available odds across all books (line-shopping).
    """
    aliases = aliases or {}
    cols = _COLUMNS[source]
    reader = csv.DictReader(io.StringIO(csv_text))
    out = []
    for row in reader:
        home = row.get("HomeTeam")
        away = row.get("AwayTeam")
        if not home or not away:
            continue
        out.append({
            "date": row.get("Date", ""),
            "home": aliases.get(home, home),
            "away": aliases.get(away, away),
            "fthg": _f(row, "FTHG"),
            "ftag": _f(row, "FTAG"),
            "o1": _f(row, *cols["o1"]),
            "ox": _f(row, *cols["ox"]),
            "o2": _f(row, *cols["o2"]),
            "oover": _f(row, *cols["oover"]),
            "ounder": _f(row, *cols["ounder"]),
        })
    return out


def get_serie_a_odds(year: int, *, refresh: bool = False,
                     source: str = "sharp") -> List[Dict]:
    """Serie A (league code I1) odds for a season, de-aliased to our names."""
    text = get_csv("I1", year, refresh=refresh)
    return parse_odds(text, SERIE_A_ALIASES, source=source)


def index_by_teams(records: List[Dict]) -> Dict[tuple, Dict]:
    """Index odds by (home, away) — a unique ordered pairing per season."""
    return {(r["home"], r["away"]): r for r in records}
