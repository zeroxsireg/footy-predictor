"""Tests for combo pricing (real quotes only), value-bet mode and market categories."""

from datetime import datetime

import pytest

from core.daily_models import DailyPick
from core.daily_league_analyzer import DailyLeagueAnalyzer
from core.pick_selector import PickSelector
from core.value_selection import MAX_STAKE_FRACTION, MIN_EV_THRESHOLD, annotate_value


def _pick(pct=60.0, odds=None, book="Bet365", market="Match Goals", conf="HIGH"):
    return DailyPick(
        match_id=1, home_team="A", away_team="B", market=market, selection="Over 1.5",
        confidence=conf, percentage=pct, reasoning="", match_time=datetime(2025, 1, 1),
        league="L", real_odds=odds, bookmaker=book if odds else None,
    )


# ── E: combos never use invented odds ────────────────────────────────────────

def test_combo_odds_multiply_real_quotes():
    sel = PickSelector()
    assert sel._calculate_combo_odds([_pick(odds=2.0), _pick(odds=1.5)]) == 3.0


def test_combo_odds_none_when_any_leg_has_no_real_quote():
    sel = PickSelector()
    assert sel._calculate_combo_odds([_pick(odds=2.0), _pick(pct=50.0)]) is None


def test_incomplete_combos_are_not_recommended_and_are_counted():
    sel = PickSelector()
    priced = [_pick(odds=1.8) for _ in range(3)]
    assert len(sel._generate_combinations(priced)) >= 1
    mixed = [_pick(odds=1.8), _pick(odds=1.8), _pick(pct=75.0)]
    assert sel._generate_combinations(mixed) == []
    assert sel.skipped_combinations >= 1
    assert sel._create_summary(mixed, mixed, [])["combinations_skipped_no_odds"] >= 1


# ── G: single value bets ─────────────────────────────────────────────────────

def test_value_pick_gets_ev_kelly_and_capped_stake():
    p = _pick(pct=60.0, odds=2.0)              # EV = +20%
    assert annotate_value(p)
    assert p.ev_percent == pytest.approx(20.0)
    assert p.kelly_quarter == pytest.approx(0.25 * 0.2, abs=1e-4)
    assert p.stake_fraction == MAX_STAKE_FRACTION   # 5% quarter-Kelly capped at 2%
    assert p.verdict == "VALUE"


def test_pick_without_real_odds_never_value():
    p = _pick(pct=99.0)
    assert not annotate_value(p)
    assert p.ev_percent is None and p.verdict is None


def test_pick_without_bookmaker_never_value():
    p = _pick(pct=60.0, odds=2.0)
    p.bookmaker = None
    assert not annotate_value(p)


def test_ev_below_tau_is_pass():
    p = _pick(pct=51.0, odds=2.0)              # EV = +2% < 3%
    assert not annotate_value(p)
    assert p.verdict == "PASS"
    assert MIN_EV_THRESHOLD == 0.03


def test_select_value_picks_sorted_by_ev_and_includes_player_cards():
    low = _pick(pct=52.0, odds=2.0)                              # EV +4%
    high = _pick(pct=60.0, odds=2.0)                             # EV +20%
    card = _pick(pct=55.0, odds=2.2, market="Player Card - Rossi")   # EV +21%
    none_odds = _pick(pct=90.0)
    losing = _pick(pct=40.0, odds=2.0)
    out = PickSelector().select_value_picks([low, none_odds, high, losing, card])
    assert out == [card, high, low]


# ── F: market categories ─────────────────────────────────────────────────────

@pytest.mark.parametrize("market,expected", [
    ("Inter Goals", "Goals"),
    ("Match Goals", "Goals"),
    ("Both Teams to Score", "BTTS"),
    ("Match Result", "Result"),
    ("Total Shots", "Shots"),
    ("Total Shots: Over 16.5", "Shots"),
    ("Inter Corners", "Corners"),
    ("Total Cards", "Cards"),
    ("Something Else", "Other"),
])
def test_market_category(market, expected):
    assert DailyLeagueAnalyzer._get_market_category(None, market) == expected
