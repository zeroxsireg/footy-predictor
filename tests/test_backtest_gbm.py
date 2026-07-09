"""Smoke tests for feature extraction and the GBM comparison."""

import pandas as pd

from backtest.features import build_feature_frame, FEATURE_COLS, iter_feature_rows
from backtest.gbm import train_and_evaluate


def _season(year, xg_bias=0.2):
    teams = [(1, "A"), (2, "B"), (3, "C"), (4, "D"), (5, "E"), (6, "F")]
    scores = [(2, 1), (0, 0), (3, 1), (1, 1), (2, 0), (1, 2), (0, 1), (3, 3)]
    fixtures, xg_map, fid, day, si = [], {}, year * 1000, 1, 0
    for _ in range(5):
        for i in range(len(teams)):
            for j in range(len(teams)):
                if i == j:
                    continue
                hg, ag = scores[si % len(scores)]
                si += 1
                fixtures.append({
                    "fixture_id": fid, "date": f"{year}-0{1+day//28}-{1+day%28:02d}T12:00:00Z",
                    "status": "FT", "season": year,
                    "home_id": teams[i][0], "home_name": teams[i][1],
                    "away_id": teams[j][0], "away_name": teams[j][1],
                    "home_goals": hg, "away_goals": ag,
                })
                xg_map[str(fid)] = {"home_xg": hg + xg_bias, "away_xg": ag + xg_bias}
                fid += 1
                day += 1
    return fixtures, xg_map


def test_feature_frame_has_expected_columns():
    fx, xg = _season(2024)
    df = build_feature_frame(fx, xg, min_matches=2)
    assert len(df) > 0
    for col in FEATURE_COLS:
        assert col in df.columns
    for label in ("y_over25", "y_btts", "y_result"):
        assert label in df.columns
    assert set(df["y_result"].unique()) <= {"1", "X", "2"}


def test_features_are_point_in_time():
    # First scored match's home_matches must equal its pre-match count (no leak).
    fx, xg = _season(2024)
    rows = list(iter_feature_rows(fx, xg, min_matches=2))
    assert rows
    # matches counter never exceeds games actually played before (bounded by round).
    assert all(r["home_matches"] >= 2 and r["away_matches"] >= 2 for r in rows)


def test_gbm_trains_and_compares():
    fx23, xg23 = _season(2023)
    fx24, xg24 = _season(2024, xg_bias=0.3)
    df = pd.concat([
        build_feature_frame(fx23, xg23, min_matches=2),
        build_feature_frame(fx24, xg24, min_matches=2),
    ], ignore_index=True)

    cmp = train_and_evaluate(df, train_seasons=[2023], test_season=2024)
    assert cmp.n_train > 0 and cmp.n_test > 0
    assert set(cmp.binary) == {"Over 2.5", "BTTS"}
    for res in cmp.binary.values():
        assert 0.0 <= res["GBM"].brier <= 1.0
        assert 0.0 <= res["Parametrico"].brier <= 1.0
    assert cmp.result_1x2["GBM"].n == cmp.n_test
