"""
Pre-match probability estimator of the lean pipeline (rule 6: probabilities only,
no odds, no stake).

Production model "xg_poisson_v1": the validated multi-season xG-fed Poisson model
with global home advantage and Bayesian shrinkage (backtest/xg_compare.iter_xg_predictions,
backtest/advanced.py: SSOT, the maths is NOT duplicated here).

Configuration (chosen on Serie A 2025 with history 2023+2024, confirmed unchanged
on Serie A 2024 with history 2023): xi = 0 (no time decay), k = 2.

Point-in-time (rule 5): only matches finished strictly before the kickoff feed the
model. The target match is appended as a placeholder record; the estimator never
reads its goals (predict-then-update), so its result cannot leak.
"""

import os
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence

import backtest.xg_compare as _xg_compare
from backtest.advanced import expected_goals
from backtest.data import DATA_DIR, cache_path, load_fixtures
from backtest.models import _markets_from_matrix, _score_matrix
from backtest.xg_compare import iter_xg_predictions
from backtest.xg_data import load_xg_map, xg_cache_path
from core.contracts import FixtureRef, MatchProbs

MODEL_ID = "xg_poisson_v1"
XI = 0.0
K_SHRINK = 2.0
P_FLOOR = 0.005


def _as_utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _parse(iso: str) -> datetime:
    return _as_utc(datetime.fromisoformat(iso.replace("Z", "+00:00")))


def _load_history(league_id: int, seasons: Sequence[int], data_dir: str):
    """Fixtures (season-tagged) and merged xG map from the offline cache; missing files are skipped."""
    fixtures: List[Dict] = []
    xg: Dict[str, Dict] = {}
    for season in seasons:
        path = os.path.join(data_dir, os.path.basename(cache_path(league_id, season)))
        if not os.path.exists(path):
            continue
        fixtures.extend(dict(rec, season=season) for rec in load_fixtures(path))
        xg_path = os.path.join(data_dir, os.path.basename(xg_cache_path(league_id, season)))
        if os.path.exists(xg_path):
            xg.update(load_xg_map(xg_path))
    return fixtures, xg


def _normalise(p1: float, px: float, p2: float) -> tuple:
    p1, px, p2 = (max(P_FLOOR, p) for p in (p1, px, p2))
    total = p1 + px + p2
    return p1 / total, px / total, p2 / total


_PATCH_LOCK = threading.Lock()


def _rows_for(fixture: FixtureRef, history_seasons, data_dir: Optional[str]):
    """Run the production model point-in-time; returns the prediction rows (target last)."""
    directory = data_dir or DATA_DIR
    seasons = sorted(set(history_seasons) | {fixture.season})
    fixtures, xg = _load_history(fixture.league_id, seasons, directory)
    kickoff = _as_utc(fixture.kickoff)

    history = [r for r in fixtures if r["fixture_id"] != fixture.fixture_id
               and _parse(r["date"]) < kickoff]
    target = {
        "fixture_id": fixture.fixture_id, "date": kickoff.isoformat(), "status": "FT",
        "home_id": fixture.home_id, "away_id": fixture.away_id,
        "home_name": fixture.home, "away_name": fixture.away,
        "home_goals": 0, "away_goals": 0,   # placeholder: never read by the estimator
        "season": fixture.season,
    }
    return list(iter_xg_predictions(
        history + [target], xg, target_season=fixture.season, xi=XI, k=K_SHRINK, min_matches=0))


def predict_fixture(fixture: FixtureRef, *, history_seasons=(2024, 2025),
                    data_dir: Optional[str] = None) -> MatchProbs:
    """P(1), P(X), P(2), P(Over 2.5) for a fixture, from matches finished before its kickoff."""
    rows = _rows_for(fixture, history_seasons, data_dir)
    probs = next(r["probs"] for r in rows if r["fixture_id"] == fixture.fixture_id)

    p1, px, p2 = _normalise(probs["result_1"], probs["result_X"], probs["result_2"])
    over = min(1.0, max(P_FLOOR, probs["over_2_5"]))
    out = MatchProbs(fixture.fixture_id, p1, px, p2, over, MODEL_ID)
    out.validate()
    return out


def predict_matrix(fixture: FixtureRef, *, history_seasons=(2024, 2025),
                   data_dir: Optional[str] = None) -> List[List[float]]:
    """Joint P(home=i, away=j), i,j in 0..MAX_GOALS, summing to 1.

    Same production configuration and point-in-time filter as predict_fixture. The
    scoring function of the shared backtest pipeline is wrapped (under a lock) only to
    capture the matrix built from the very same expected goals; the maths stays in
    backtest.advanced / backtest.models (SSOT).
    """
    captured: List[List[List[float]]] = []

    def capture(ctx, k: float = 5.0, rho: float = 0.0):
        lam_home, lam_away = expected_goals(ctx, k=k)
        matrix = _score_matrix(lam_home, lam_away, rho=0.0)
        captured.append(matrix)
        return _markets_from_matrix(matrix)

    with _PATCH_LOCK:
        original = _xg_compare.strength_predict
        _xg_compare.strength_predict = capture
        try:
            _rows_for(fixture, history_seasons, data_dir)
        finally:
            _xg_compare.strength_predict = original
    matrix = captured[-1]           # the target is chronologically last: predicted last
    total = sum(sum(row) for row in matrix)
    return [[v / total for v in row] for row in matrix]     # tail beyond MAX_GOALS is < 1e-4
