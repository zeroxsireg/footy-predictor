"""
Gradient-boosting model over the engineered features.

Trains HistGradientBoosting on past seasons and evaluates out-of-sample on a
held-out season (time-split -> no leakage, since features are point-in-time).
Compares the GBM against the parametric xG model, whose own probabilities are
among the features (columns pois_*) — so the baseline is scored on the exact
same test matches.
"""

from dataclasses import dataclass
from typing import Dict, List

import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier

from backtest.features import FEATURE_COLS
from backtest.metrics import (
    BinaryMarketResult, MulticlassMarketResult, score_binary, score_multiclass,
)

_CLASSES_1X2 = ("1", "X", "2")


def _make_clf():
    # Heavily regularised: shallow trees, large leaves, strong L2, early stopping.
    # Football is low signal-to-noise, so we fight overfitting hard.
    return HistGradientBoostingClassifier(
        max_iter=500, learning_rate=0.03, max_depth=2,
        min_samples_leaf=60, l2_regularization=5.0,
        early_stopping=True, validation_fraction=0.15, n_iter_no_change=20,
        random_state=42,
    )


@dataclass
class GbmComparison:
    n_train: int
    n_test: int
    binary: Dict[str, Dict[str, BinaryMarketResult]]   # market -> {"GBM":..,"Parametrico":..}
    result_1x2: Dict[str, MulticlassMarketResult]        # {"GBM":.., "Parametrico":..}


def _fit_binary(train: pd.DataFrame, test: pd.DataFrame, label: str):
    clf = _make_clf()
    clf.fit(train[FEATURE_COLS], train[label])
    idx1 = list(clf.classes_).index(1)
    return clf.predict_proba(test[FEATURE_COLS])[:, idx1]


def _fit_multiclass(train: pd.DataFrame, test: pd.DataFrame):
    clf = _make_clf()
    clf.fit(train[FEATURE_COLS], train["y_result"])
    classes = list(clf.classes_)
    proba = clf.predict_proba(test[FEATURE_COLS])
    return [
        {c: proba[i, classes.index(c)] for c in _CLASSES_1X2}
        for i in range(len(test))
    ]


def train_and_evaluate(
    df: pd.DataFrame, train_seasons: List[int], test_season: int,
) -> GbmComparison:
    train = df[df["season"].isin(train_seasons)].reset_index(drop=True)
    test = df[df["season"] == test_season].reset_index(drop=True)

    binary: Dict[str, Dict[str, BinaryMarketResult]] = {}
    for market, label, pois_col in [
        ("Over 2.5", "y_over25", "pois_over25"),
        ("BTTS", "y_btts", "pois_btts"),
    ]:
        gbm_p = _fit_binary(train, test, label)
        y = test[label].tolist()
        binary[market] = {
            "GBM": score_binary(market, list(zip(gbm_p, y))),
            "Parametrico": score_binary(market, list(zip(test[pois_col].tolist(), y))),
        }

    gbm_1x2 = _fit_multiclass(train, test)
    actual = test["y_result"].tolist()
    param_1x2 = [
        {"1": r["pois_p1"], "X": r["pois_pX"], "2": r["pois_p2"]}
        for r in test.to_dict("records")
    ]
    result_1x2 = {
        "GBM": score_multiclass("1X2", list(zip(gbm_1x2, actual))),
        "Parametrico": score_multiclass("1X2", list(zip(param_1x2, actual))),
    }

    return GbmComparison(
        n_train=len(train), n_test=len(test),
        binary=binary, result_1x2=result_1x2,
    )
