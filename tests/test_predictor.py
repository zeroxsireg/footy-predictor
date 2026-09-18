"""Tests for core.predictor: parity with the backtest, point-in-time, validity (offline)."""

import json
import os
from collections import Counter
from datetime import datetime, timedelta, timezone

import pytest

from backtest.ablation import load_seasons
from backtest.data import DATA_DIR
from backtest.xg_compare import iter_xg_predictions
from backtest.xg_data import load_xg_map, xg_cache_path
from core.contracts import FixtureRef
from core.predictor import K_SHRINK, MODEL_ID, XI, predict_fixture

TEAMS = [1, 2, 3, 4]


def _rec(fid, day, home, away, hg, ag):
    date = (datetime(2025, 1, 1, 18, tzinfo=timezone.utc) + timedelta(days=day)).isoformat()
    return {"fixture_id": fid, "date": date, "status": "FT", "home_id": home, "away_id": away,
            "home_name": f"T{home}", "away_name": f"T{away}", "home_goals": hg, "away_goals": ag}


def _history(overrides=None):
    recs, fid = [], 100
    for day in range(12):
        home, away = TEAMS[day % 4], TEAMS[(day + 1 + day // 4) % 4]
        if home == away:
            away = TEAMS[(TEAMS.index(home) + 1) % 4]
        recs.append(_rec(fid, day, home, away, (day * 3) % 4, (day * 5) % 3))
        fid += 1
    return recs


def _write(tmp_path, recs):
    (tmp_path / "league_135_season_2025.json").write_text(json.dumps(recs))
    return str(tmp_path)


def _fixture(day=13):
    kick = datetime(2025, 1, 1, 18, tzinfo=timezone.utc) + timedelta(days=day)
    return FixtureRef(9999, kick, "T1", "T2", 1, 2, 135, 2025)


def test_output_is_valid_and_labelled(tmp_path):
    out = predict_fixture(_fixture(), history_seasons=(2025,), data_dir=_write(tmp_path, _history()))
    out.validate()
    assert out.model == MODEL_ID == "xg_poisson_v1"
    assert out.fixture_id == 9999
    assert 0 < out.p_over_2_5 < 1


def test_missing_history_files_still_predicts(tmp_path):
    out = predict_fixture(_fixture(), history_seasons=(2023, 2024), data_dir=str(tmp_path))
    out.validate()
    assert abs(out.p1 + out.px + out.p2 - 1) < 1e-9


def test_future_results_do_not_change_probabilities(tmp_path):
    recs = _history()
    fx = _fixture(day=6)     # matches on days > 6 are in the future
    base = predict_fixture(fx, history_seasons=(2025,), data_dir=_write(tmp_path, recs))
    altered = [dict(r, home_goals=9, away_goals=0) if r["date"] > fx.kickoff.isoformat() else r
               for r in recs]
    after = predict_fixture(fx, history_seasons=(2025,), data_dir=_write(tmp_path, altered))
    assert (after.p1, after.px, after.p2, after.p_over_2_5) == (base.p1, base.px, base.p2, base.p_over_2_5)


def test_past_results_do_change_probabilities(tmp_path):
    """Positive control: the leakage test above can fail."""
    recs = _history()
    fx = _fixture(day=6)
    base = predict_fixture(fx, history_seasons=(2025,), data_dir=_write(tmp_path, recs))
    altered = [dict(r, home_goals=9, away_goals=0) if r["date"] < fx.kickoff.isoformat() else r
               for r in recs]
    after = predict_fixture(fx, history_seasons=(2025,), data_dir=_write(tmp_path, altered))
    assert after.p1 != base.p1


def test_pinned_configuration():
    assert (XI, K_SHRINK) == (0.0, 2.0)   # chosen on Serie A 2025, confirmed on 2024


def test_simultaneous_kickoff_result_is_not_used(tmp_path):
    recs = _history()
    fx = _fixture(day=6)
    twin = _rec(1, 6, 3, 4, 9, 0)      # same kickoff, lower fixture id: not finished yet
    a = predict_fixture(fx, history_seasons=(2025,), data_dir=_write(tmp_path, recs))
    b = predict_fixture(fx, history_seasons=(2025,), data_dir=_write(tmp_path, recs + [twin]))
    assert a == b


def test_match_finished_after_kickoff_is_ignored_even_if_same_id(tmp_path):
    recs = _history()
    fx = _fixture(day=6)
    same_id = dict(recs[8], fixture_id=fx.fixture_id, home_goals=8)   # after kickoff
    a = predict_fixture(fx, history_seasons=(2025,), data_dir=_write(tmp_path, recs))
    b = predict_fixture(fx, history_seasons=(2025,), data_dir=_write(tmp_path, recs + [same_id]))
    assert a == b


def test_parity_with_backtest_on_real_2025_matches():
    """predict_fixture(as_of = kickoff) == iter_xg_predictions for played 2025 matches (read-only)."""
    seasons = [2024, 2025]
    fixtures = load_seasons(135, seasons)
    xg = {}
    for s in seasons:
        xg.update(load_xg_map(xg_cache_path(135, s)))
    kickoffs = Counter(r["date"] for r in fixtures)
    reference = {p["fixture_id"]: p["probs"] for p in
                 iter_xg_predictions(fixtures, xg, target_season=2025, xi=XI, k=K_SHRINK)}
    checked = 0
    for rec in fixtures:
        if rec["season"] != 2025 or kickoffs[rec["date"]] > 1 or rec["fixture_id"] not in reference:
            continue
        if checked >= 4:
            break
        fx = FixtureRef(rec["fixture_id"], datetime.fromisoformat(rec["date"]), rec["home_name"],
                        rec["away_name"], rec["home_id"], rec["away_id"], 135, 2025)
        got = predict_fixture(fx, history_seasons=(2024,), data_dir=DATA_DIR)
        ref = reference[rec["fixture_id"]]
        assert got.p1 == pytest.approx(ref["result_1"], abs=1e-9)
        assert got.px == pytest.approx(ref["result_X"], abs=1e-9)
        assert got.p2 == pytest.approx(ref["result_2"], abs=1e-9)
        assert got.p_over_2_5 == pytest.approx(ref["over_2_5"], abs=1e-9)
        checked += 1
    assert checked == 4
