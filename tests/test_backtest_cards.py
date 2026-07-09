"""Tests for cards parsing and the team cards model."""

from backtest.cards_data import _extract_cards
from backtest.cards import run_cards_backtest, _ref_name, _shrunk, _clamp, LINES


# ── parsing ───────────────────────────────────────────────────────────────────

def _entry(tid, yellows):
    return {"team": {"id": tid}, "statistics": [
        {"type": "Total Shots", "value": 10},
        {"type": "Yellow Cards", "value": yellows},
    ]}


def test_extract_cards():
    resp = [_entry(1, 2), _entry(2, 3)]
    assert _extract_cards(resp, 1, 2) == (2, 3)


def test_extract_cards_missing():
    resp = [_entry(1, None)]
    assert _extract_cards(resp, 1, 2) == (0, None)  # None value -> 0; away absent -> None


def test_ref_name_strips_country():
    assert _ref_name("R. Abisso, Italy") == "R. Abisso"
    assert _ref_name("Daniele Orsato") == "Daniele Orsato"
    assert _ref_name(None) == ""


def test_shrinkage_and_clamp():
    assert _shrunk(0.0, 0.0, prior=4.0, k=8.0) == 4.0     # no data -> prior
    assert _clamp(5.0) == 1.8 and _clamp(0.1) == 0.5


# ── backtest ──────────────────────────────────────────────────────────────────

def _season(referee_cycle=("Ref A", "Ref B")):
    teams = [(1, "A"), (2, "B"), (3, "C"), (4, "D")]
    card_counts = [(2, 2), (1, 3), (3, 1), (2, 4), (0, 2), (3, 3)]
    fixtures, cards, fid, day, si = [], {}, 1, 1, 0
    for _ in range(6):
        for i in range(len(teams)):
            for j in range(len(teams)):
                if i == j:
                    continue
                hc, ac = card_counts[si % len(card_counts)]
                fixtures.append({
                    "fixture_id": fid, "date": f"2024-0{1+day//28}-{1+day%28:02d}T12:00:00Z",
                    "status": "FT", "season": 2024,
                    "home_id": teams[i][0], "away_id": teams[j][0],
                    "home_name": teams[i][1], "away_name": teams[j][1],
                    "referee": referee_cycle[si % len(referee_cycle)],
                })
                cards[str(fid)] = {"home_cards": hc, "away_cards": ac}
                si += 1
                fid += 1
                day += 1
    return fixtures, cards


def test_cards_backtest_runs_and_scores_lines():
    fx, cards = _season()
    rep = run_cards_backtest(fx, cards, min_matches=2)
    assert rep.n > 0
    assert len(rep.lines) == len(LINES)
    assert rep.avg_expected > 0 and rep.avg_actual > 0
    assert rep.mae >= 0
    assert 0.0 <= rep.ref_coverage <= 1.0
    for line in rep.lines:
        assert 0.0 <= line.base_rate <= 1.0


def test_cards_backtest_skips_matches_without_card_data():
    fx, cards = _season()
    for fid in list(cards)[::2]:
        cards[fid] = {"home_cards": None, "away_cards": None}
    rep = run_cards_backtest(fx, cards, min_matches=2)
    assert rep.n > 0   # still scores the matches that have data
