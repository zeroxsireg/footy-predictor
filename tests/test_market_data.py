"""market_data: quotes (priority/fallback/benchmark), results, lineups, probable XI, refresh.

Only saved real payloads (tests/fixtures/market_*.json) and fakes: no network, no real DB/data.
"""

import asyncio
import copy, json, os
from pathlib import Path

import pytest

from core import market_data, market_http, market_prices
from core.contracts import MARKET_1X2, MARKET_OU25

FIX = Path(__file__).parent / "fixtures"


def load(name):
    return json.loads((FIX / name).read_text())


class FakeClient:
    """Maps (endpoint, sorted params) -> payload; records calls; `raise_all` simulates outages."""
    def __init__(self, routes=None, raise_all=False):
        self.routes, self.calls, self.raise_all = routes or {}, [], raise_all

    async def request(self, endpoint, params=None):
        self.calls.append((endpoint, dict(params)))
        if self.raise_all:
            raise RuntimeError("boom")
        key = (endpoint, tuple(sorted(params.items())))
        if key not in self.routes:
            return {"response": []}
        return {"response": self.routes[key]}


class MemCache:
    def __init__(self):
        self.d = {}

    async def get_data(self, key, ttl_type=None):
        return self.d.get(key)

    async def set_data(self, key, data, ttl_type):
        self.d[key] = data
        return True


def route(endpoint, response, **params):
    return (endpoint, tuple(sorted(params.items()))), response


@pytest.fixture(autouse=True)
def isolated():
    market_http.set_cache(MemCache())
    yield
    market_http.set_client(None)
    market_http.set_cache(None)


def use(*routes, **kw):
    client = FakeClient(dict(routes), **kw)
    market_http.set_client(client)
    return client


def run(coro):
    return asyncio.run(coro)


def books():
    return copy.deepcopy(load("market_odds_1550135.json")["response"][0]["bookmakers"])


def odds_route(bookmakers):
    return route("/odds", [{"bookmakers": bookmakers}], fixture=1550135)


# ---------------------------------------------------------------- prices
def test_prices_real_payload_bet365_single_bookmaker():
    use(route("/odds", load("market_odds_1550135.json")["response"], fixture=1550135))
    q = run(market_data.get_prices(1550135))
    assert q[MARKET_1X2].bookmaker == "Bet365" and q[MARKET_1X2].bookmaker_id == 8
    assert q[MARKET_1X2].odds == {"1": 2.25, "X": 3.30, "2": 3.30}
    assert q[MARKET_OU25].odds == {"over": 2.10, "under": 1.73}
    assert q[MARKET_1X2].captured_at.tzinfo is not None


def test_priority_falls_through_bwin_then_william_hill():
    bs = [b for b in books() if b["id"] != 8]           # no Bet365, no Bwin in payload
    assert market_prices.select_quotes(1, bs)[MARKET_1X2].bookmaker_id == 7
    bs = [b for b in books() if b["id"] == 3]
    assert market_prices.select_quotes(1, bs)[MARKET_1X2].bookmaker_id == 3


def test_never_mixes_bookmakers_incomplete_priority_market_skipped():
    bs = books()
    bet365 = next(b for b in bs if b["id"] == 8)
    bet365["bets"][0]["values"] = [v for v in bet365["bets"][0]["values"] if v["value"] != "Draw"]
    q = market_prices.select_quotes(1, bs)
    wh = next(b for b in bs if b["id"] == 7)["bets"][0]["values"]
    assert q[MARKET_1X2].bookmaker_id == 7
    assert q[MARKET_1X2].odds == {k: float(v["odd"]) for k, v in zip("1X2", wh)}
    assert q[MARKET_OU25].bookmaker_id == 8            # other market still Bet365


def test_fallback_to_non_priority_bookmaker_with_all_selections():
    bs = [b for b in books() if b["id"] == 4]           # only Pinnacle-like id 4 present
    q = market_prices.select_quotes(1, bs)
    assert q[MARKET_1X2].bookmaker_id == 4


def test_absent_market_means_absent_key_and_failure_is_empty():
    bs = books()
    for b in bs:
        b["bets"] = [x for x in b["bets"] if x["id"] == 1]
    use(odds_route(bs))
    q = run(market_data.get_prices(1550135))
    assert set(q) == {MARKET_1X2}
    use(raise_all=True)
    market_http.set_cache(MemCache())
    assert run(market_data.get_prices(1550135)) == {}
    assert run(market_data.get_benchmark_prices(1550135)) == {}


def test_benchmark_is_pinnacle_only():
    use(odds_route(books()))
    q = run(market_data.get_benchmark_prices(1550135))
    assert q[MARKET_1X2].bookmaker == "Pinnacle" and q[MARKET_1X2].odds["1"] == 2.29
    assert q[MARKET_OU25].odds == {"over": 2.19, "under": 1.73}
    use(odds_route([b for b in books() if b["id"] != 4]))
    market_http.set_cache(MemCache())
    assert run(market_data.get_benchmark_prices(1550135)) == {}


def test_odds_cached_within_ttl_and_refetched_after(monkeypatch):
    client = use(odds_route(books()))
    run(market_data.get_prices(1550135))
    run(market_data.get_benchmark_prices(1550135))
    assert len(client.calls) == 1
    import time
    real = time.time()
    monkeypatch.setattr(time, "time", lambda: real + 601)
    run(market_data.get_prices(1550135))
    assert len(client.calls) == 2


# ---------------------------------------------------------------- results / lineups
def fixture_item(status, home=2, away=1):
    return [{"fixture": {"status": {"short": status}}, "goals": {"home": home, "away": away}}]


def test_result_finished_lists_yellow_players_from_real_payload():
    use(route("/fixtures", fixture_item("FT"), id=1550120),
        route("/fixtures/players", load("market_players_1550120.json")["response"], fixture=1550120))
    r = run(market_data.get_result(1550120))
    assert r.finished and (r.home_goals, r.away_goals) == (2, 1)
    assert r.booked_player_ids == [1457, 19185]


def test_result_not_finished_skips_players_and_missing_is_none():
    client = use(route("/fixtures", fixture_item("NS", None, None), id=7))
    r = run(market_data.get_result(7))
    assert not r.finished and r.booked_player_ids == [] and len(client.calls) == 1
    assert run(market_data.get_result(999)) is None


def test_result_withheld_when_players_lookup_fails():
    use(route("/fixtures", fixture_item("FT"), id=5))   # /fixtures/players -> empty
    assert run(market_data.get_result(5)) is None


def test_lineups_real_payload_and_not_available():
    use(route("/fixtures/lineups", load("market_lineups_1550120.json")["response"], fixture=1550120))
    lu = run(market_data.get_lineups(1550120))
    assert set(lu) == {505, lu_other(lu)}
    assert sum(p["starter"] for p in lu[505]) == 11
    assert {"id", "name", "position", "starter"} == set(lu[505][0])
    use()
    assert run(market_data.get_lineups(1)) is None


def lu_other(lu):
    return next(k for k in lu if k != 505)


# ---------------------------------------------------------------- probable XI
def players_payload(team_id, rows):
    return [{"team": {"id": team_id}, "players": [
        {"player": {"id": pid, "name": f"P{pid}"},
         "statistics": [{"games": {"minutes": m, "substitute": sub, "position": "M"}, "cards": {"yellow": 0}}]}
        for pid, m, sub in rows]}]


def test_probable_xi_shares_and_permanent_cache():
    last = [{"fixture": {"id": i, "status": {"short": "FT"}}} for i in (1, 2, 3)]
    client = use(
        route("/fixtures", last, team=9, season=2026, last=3),
        route("/fixtures/players", players_payload(9, [(10, 90, False), (11, 45, False), (12, 45, True)]), fixture=1),
        route("/fixtures/players", players_payload(9, [(10, 90, False), (12, 90, False)]), fixture=2),
        route("/fixtures/players", players_payload(9, [(10, 60, False), (11, None, True)]), fixture=3))
    xi = run(market_data.get_probable_xi(9, 2026, 3))
    by = {p["id"]: p for p in xi}
    assert [p["id"] for p in xi][0] == 10 and by[10]["start_share"] == 1.0
    assert by[10]["minutes_share"] == pytest.approx(240 / 270)
    assert by[11]["start_share"] == pytest.approx(1 / 3) and by[11]["minutes_share"] == pytest.approx(45 / 270)
    assert by[12]["start_share"] == pytest.approx(1 / 3) and by[12]["minutes_share"] == pytest.approx(135 / 270)
    n_players = sum(c[0] == "/fixtures/players" for c in client.calls)
    run(market_data.get_probable_xi(9, 2026, 3))
    assert sum(c[0] == "/fixtures/players" for c in client.calls) == n_players == 3


def test_probable_xi_ignores_unfinished_and_failure_is_empty():
    last = [{"fixture": {"id": 1, "status": {"short": "1H"}}}]
    use(route("/fixtures", last, team=9, season=2026, last=3))
    assert run(market_data.get_probable_xi(9, 2026, 3)) == []
    last = [{"fixture": {"id": 1, "status": {"short": "FT"}}}, {"fixture": {"id": 2, "status": {"short": "1H"}}}]
    use(route("/fixtures", last, team=9, season=2026, last=3),
        route("/fixtures/players", players_payload(9, [(10, 90, False)]), fixture=1),
        route("/fixtures/players", players_payload(9, [(11, 90, False)]), fixture=2))
    market_http.set_cache(MemCache())
    xi = run(market_data.get_probable_xi(9, 2026, 3))
    assert [(p["id"], p["start_share"], p["minutes_share"]) for p in xi] == [(10, 1.0, 1.0)]  # 1 finished game found
    use(raise_all=True)
    market_http.set_cache(MemCache())
    assert run(market_data.get_probable_xi(9, 2026, 3)) == []


# ---------------------------------------------------------------- upcoming
def test_upcoming_fixtures_parse_and_filter():
    def item(fid, date, ref, status="NS"):
        return {"fixture": {"id": fid, "date": date, "referee": ref, "status": {"short": status}},
                "league": {"round": "Regular Season - 5"},
                "teams": {"home": {"id": 1, "name": "A"}, "away": {"id": 2, "name": "B"}}}
    payload = [item(2, "2026-09-20T13:00:00+02:00", None), item(1, "2026-09-19T13:00:00+00:00", "D. Massa"),
               item(3, "2026-09-19T14:00:00+00:00", None, "PST")]
    market_http.set_client(_Any(payload))
    fx = run(market_data.get_upcoming_fixtures(days=3))
    assert [f.fixture_id for f in fx] == [1, 2]
    assert fx[0].referee == "D. Massa" and fx[1].referee is None
    assert fx[1].kickoff.utcoffset().total_seconds() == 0 and fx[1].kickoff.hour == 11
    assert fx[0].round == "Regular Season - 5" and fx[0].league_id == 135 and fx[0].season == 2026


class _Any:
    def __init__(self, response):
        self.response = response

    async def request(self, endpoint, params=None):
        return {"response": self.response}


# ---------------------------------------------------------------- refresh
def rec(fid, status="FT"):
    return {"fixture_id": fid, "status": status, "home_id": 1, "away_id": 2}


def stats(h, a):
    mk = lambda tid, v: {"team": {"id": tid}, "statistics": [{"type": "expected_goals", "value": v}]}
    return [mk(1, h), mk(2, a)]


@pytest.fixture
def datadir(tmp_path, monkeypatch):
    from backtest import data, xg_data
    monkeypatch.setattr(data, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(xg_data, "DATA_DIR", str(tmp_path))
    return tmp_path


def test_refresh_is_incremental_and_never_rewrites_existing(datadir, monkeypatch):
    from backtest import data
    async def fake_fetch(league, season):
        return [rec(1), rec(2), rec(3, "NS")]
    monkeypatch.setattr(data, "fetch_season_fixtures", fake_fetch)
    xg_file = datadir / "xg_league_135_season_2026.json"
    xg_file.write_text(json.dumps({"1": {"home_xg": 9.9, "away_xg": 8.8}}))
    client = use(route("/fixtures/statistics", stats("1.30", "0.70"), fixture=2))
    s = run(market_data.refresh_current_season_data())
    assert s == {"fixtures": 3, "xg_added": 1, "api_calls": 2}
    saved = json.loads(xg_file.read_text())
    assert saved["1"] == {"home_xg": 9.9, "away_xg": 8.8}
    assert saved["2"] == {"home_xg": 1.3, "away_xg": 0.7} and "3" not in saved
    assert [c[1]["fixture"] for c in client.calls] == [2]
    assert len(json.loads((datadir / "league_135_season_2026.json").read_text())) == 3


def test_refresh_refuses_historical_and_keeps_file_on_empty_download(datadir, monkeypatch):
    from backtest import data
    client = use()
    s = run(market_data.refresh_current_season_data(season=2025))
    assert s["fixtures"] == 0 and "error" in s and not os.listdir(datadir) and client.calls == []
    async def empty(league, season):
        return []
    monkeypatch.setattr(data, "fetch_season_fixtures", empty)
    keep = datadir / "league_135_season_2026.json"
    keep.write_text("[1]")
    run(market_data.refresh_current_season_data())
    assert keep.read_text() == "[1]"
