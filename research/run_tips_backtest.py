"""
Measure every tip market out of sample and print the table (and MEASURED source).

    python -m research.run_tips_backtest [--source]

Read-only on backtest/data; no network.
"""

import sys
import statistics as st

from backtest.metrics import rps_1x2
from core.contracts import TIP_CATALOG
from core.tip_measure import collect, measure
from core.tip_reliability import BAND, label_reliability


def _band(b):
    return f"n={b['n']:4d} prev {b['pred']:.0%} reale {b['real']:.0%}" if b else "-"


def main() -> None:
    rows = collect()
    res = measure(rows)
    rps = st.mean(rps_1x2({"1": r["probs"]["result_1"], "X": r["probs"]["result_X"],
                           "2": r["probs"]["result_2"]},
                          "1" if r["home_goals"] > r["away_goals"]
                          else "X" if r["home_goals"] == r["away_goals"] else "2")
                  for r in rows)
    brier = st.mean((r["probs"]["over_2_5"] - (1 if r["home_goals"] + r["away_goals"] > 2 else 0)) ** 2
                    for r in rows)
    mass = min(sum(map(sum, r["matrix"])) for r in rows)
    print(f"partite: {len(rows)}  RPS 1X2: {rps:.4f}  Brier Over2.5: {brier:.4f}  "
          f"massa minima matrice troncata: {mass:.6f}")
    for name in [k for k in res if k.startswith("@")] + list(TIP_CATALOG):
        s = res[name]
        lab = label_reliability(s["skill"], s["bands"][BAND])
        print(f"{name:16s} {lab:5s} skill {s['skill']:+.3f} freq {s['freq']:.1%} "
              f"pmed {s['p_mean']:.1%} | >=60 {_band(s['bands'][0.60])} | "
              f">=75 {_band(s['bands'][0.75])} | >=85 {_band(s['bands'][0.85])}")
    if "--source" in sys.argv:
        for key in TIP_CATALOG:
            s = res[key]
            lab = label_reliability(s["skill"], s["bands"][BAND])
            print(f'    "{key}": {{"reliability": "{lab}", "skill": {s["skill"]:.3f}, '
                  f'"n": {s["n"]}, "freq": {s["freq"]:.3f}}},')


if __name__ == "__main__":
    main()
