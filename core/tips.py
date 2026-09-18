"""
"Probable picks" of one fixture (rule 6: probabilities only, no market quotes).

Every key of core.contracts.TIP_CATALOG is priced directly from the joint score matrix
of the production model (core.predictor.predict_matrix); the market definitions live in
core/tip_defs.py. min_odds is the quote at or above which the pick has EV >= TIP_MIN_EDGE.
"""

from typing import List, Optional

from core.contracts import TIP_CATALOG, TIP_MIN_EDGE, FixtureRef, Tip
from core.tip_defs import tip_probability
from core.tip_reliability import reliability_of

P_MIN, P_MAX = 0.005, 0.995


def tips_for_fixture(fixture: FixtureRef,
                     matrix: Optional[List[List[float]]] = None) -> List[Tip]:
    if matrix is None:
        from core.predictor import predict_matrix    # lazy: keeps this module offline-testable
        matrix = predict_matrix(fixture)
    tips: List[Tip] = []
    for key, (label, family) in TIP_CATALOG.items():
        p = min(P_MAX, max(P_MIN, tip_probability(matrix, key)))
        fair = 1.0 / p
        tips.append(Tip(fixture.fixture_id, key, label, family, p, fair,
                        fair * (1.0 + TIP_MIN_EDGE), reliability_of(key)))
    return tips
