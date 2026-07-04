"""
Offline backtesting for the footy-predictor model.

Level 1 (accuracy): replays a completed season match-by-match, reconstructing
each team's statistics *as they were before every match* (no look-ahead /
data-leakage), runs the real prediction maths, and scores the predictions
against actual results (Brier score, hit-rate, calibration).

No betting odds are needed at this level — this measures whether the model
*predicts* well, which is the prerequisite for it being *profitable*.
"""
