#!/usr/bin/env python3
"""
Generate the prediction JSON for a matchday across leagues.

Writes predictions/league_<id>/season_<yr>/round_<n>.json — the data contract
the frontend (Fase 3) will consume.

Usage:
    python generate_json.py --round 20
    python generate_json.py --leagues 135,140 --season 2024 --round 20
"""

import argparse

from backtest.export import export_round

DEFAULT_LEAGUES = "135,140,39"   # Serie A, La Liga, Premier (full markets)


def parse_args():
    p = argparse.ArgumentParser(description="Generate prediction JSON")
    p.add_argument("--leagues", type=str, default=DEFAULT_LEAGUES)
    p.add_argument("--season", type=int, default=2024)
    p.add_argument("--history", type=str, default="2023")
    p.add_argument("--round", type=int, required=True)
    p.add_argument("--out", type=str, default="predictions")
    return p.parse_args()


def main():
    args = parse_args()
    leagues = [int(x) for x in args.leagues.split(",") if x.strip()]
    history = [int(s) for s in args.history.split(",") if s.strip()]

    for lid in leagues:
        try:
            path, n = export_round(lid, season=args.season, history_seasons=history,
                                   matchday=args.round, out_dir=args.out)
            print(f"✅ lega {lid}: {n} partite → {path}")
        except FileNotFoundError:
            print(f"⚠️ lega {lid}: dati mancanti, saltata")
        except Exception as exc:
            print(f"❌ lega {lid}: errore {exc}")


if __name__ == "__main__":
    main()
