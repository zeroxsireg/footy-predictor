"""Tests for core.referee (offline, synthetic cache in tmp_path)."""

import json
from datetime import datetime, timezone

from core.referee import strictness


def _write(tmp_path, matches):
    fixtures, cards = [], {}
    for i, (day, ref, total) in enumerate(matches):
        fid = 1000 + i
        fixtures.append({"fixture_id": fid, "date": f"2024-01-{day:02d}T18:00:00+00:00",
                         "status": "FT", "referee": ref})
        cards[str(fid)] = {"home_cards": total, "away_cards": 0}
    (tmp_path / "league_135_season_2024.json").write_text(json.dumps(fixtures))
    (tmp_path / "cards_league_135_season_2024.json").write_text(json.dumps(cards))
    return str(tmp_path)


MATCHES = [(d, "A. Strict, Italy", 8) for d in range(1, 11)] + \
          [(d, "B. Lenient", 2) for d in range(11, 21)] + [(d, "C. Mid", 5) for d in range(21, 28)]


def test_strict_above_lenient_below_and_clamped(tmp_path):
    d = _write(tmp_path, MATCHES)
    assert strictness("A. Strict", data_dir=d) > 1.15
    assert strictness("B. Lenient", data_dir=d) < 0.85
    assert 0.6 <= strictness("B. Lenient", data_dir=d) <= strictness("A. Strict", data_dir=d) <= 1.6


def test_unknown_or_missing_referee_is_neutral(tmp_path):
    d = _write(tmp_path, MATCHES)
    assert strictness("Nobody", data_dir=d) == 1.0
    assert strictness(None, data_dir=d) == 1.0
    assert strictness("A. Strict", data_dir=str(tmp_path / "empty")) == 1.0


def test_shrinks_toward_one_with_few_matches(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    many = _write(tmp_path / "a", MATCHES)
    few = _write(tmp_path / "b", MATCHES[:1] + MATCHES[10:])   # strict ref only 1 match
    assert 1.0 < strictness("A. Strict", data_dir=few) < strictness("A. Strict", data_dir=many)


def test_point_in_time_ignores_matches_from_before_date_onward(tmp_path):
    d = _write(tmp_path, MATCHES)
    cutoff = datetime(2024, 1, 11, 0, tzinfo=timezone.utc)   # only the strict ref's matches precede
    assert strictness("B. Lenient", before_date=cutoff, data_dir=d) == 1.0   # no matches yet
    assert strictness("A. Strict", before_date=cutoff, data_dir=d) >= 1.0
    later = datetime(2024, 1, 25, tzinfo=timezone.utc)
    assert strictness("B. Lenient", before_date=later, data_dir=d) < 1.0
