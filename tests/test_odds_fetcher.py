"""OddsFetcher: bookmaker priority, per-team markets, player-booked odds, cache/offline."""

import copy
from datetime import datetime

import pytest

from core.odds_fetcher import OddsFetcher
from core.odds_names import normalize_player_name
from core.odds_player_booked import parse_booked_value, select_player_quotes
from tests.odds_helpers import DeadRedis, FakeOddsClient, load_fixture


def team_payload():
    return load_fixture("odds_team_markets_roma_inter.json")


def make_fetcher(payload, **kw):
    client = FakeOddsClient(payload, **kw.pop("client_kw", {}))
    return OddsFetcher(odds_client=client, redis_cache=kw.pop("redis_cache", None)), client


# ── rule 11: priority, not best price ────────────────────────────────────────

async def test_bet365_assigned_even_when_other_book_pays_more():
    payload = team_payload()
    # Cards O/U (80): make 1xBet clearly better than Bet365
    for bm in payload["response"][0]["bookmakers"]:
        for bet in bm["bets"]:
            if bet["id"] == 80:
                for v in bet["values"]:
                    if v["value"] == "Over 3.5":
                        v["odd"] = {"Bet365": "1.73", "1xBet": "2.40", "Pinnacle": "2.10"}[bm["name"]]
    fetcher, _ = make_fetcher(payload)
    quote = await fetcher.get_odds_for_market(1, "Total Cards", "Over 3.5")
    assert (quote.bookmaker_name, quote.bookmaker_id, quote.odds) == ("Bet365", 8, 1.73)


async def test_priority_order_bwin_then_william_hill_then_betfair_then_first_available():
    fetcher, _ = make_fetcher(team_payload())

    def book(bid, name, odd):
        from adapters.odds_api import BookmakerOdds
        return BookmakerOdds(bid, name, 80, "Cards Over/Under", [{"value": "Over 3.5", "odd": odd}])

    async def run(books):
        from adapters.odds_api import FixtureOdds
        fetcher.odds_client.get_fixture_odds = _returning(FixtureOdds(1, books))
        return await fetcher._fetch_from_bookmakers(1, 80, "Over 3.5")

    other = book(11, "1xBet", "3.00")
    assert (await run([other, book(3, "Betfair", "2.0"), book(7, "William Hill", "1.9"), book(6, "Bwin", "1.8")]))[0] == "Bwin"
    assert (await run([other, book(3, "Betfair", "2.0"), book(7, "William Hill", "1.9")]))[0] == "William Hill"
    assert (await run([other, book(3, "Betfair", "2.0")]))[0] == "Betfair"
    first_available = await run([book(36, "BetVictor", "1.5"), book(11, "1xBet", "3.00")])
    assert first_available[0] == "BetVictor"      # fallback: first in payload, not the best price


def _returning(value):
    async def fn(**kwargs):
        return value
    return fn


# ── team markets hit the per-team bet id ─────────────────────────────────────

@pytest.mark.parametrize("market, selection, bet_id, expected_odds", [
    ("AS Roma Corners", "Over 4.5", 57, 1.91),   # home -> 57 (NOT total corners 45)
    ("AS Roma Cards", "Over 2.5", 82, 2.50),      # home -> 82 (NOT total cards 80)
])
async def test_team_markets_use_team_bet_id(market, selection, bet_id, expected_odds):
    fetcher, client = make_fetcher(team_payload())
    quote = await fetcher.get_odds_for_market(1, market, selection)
    assert ("odds", 1, (bet_id,)) in client.calls
    if expected_odds is not None:
        assert quote.odds == expected_odds


async def test_unmapped_team_market_returns_none_without_api_call_and_warns_once(capsys):
    fetcher, client = make_fetcher(team_payload())
    assert await fetcher.get_odds_for_market(1, "Inter Shots", "Over 10.5") is None
    assert await fetcher.get_odds_for_market(1, "AS Roma Shots", "Over 9.5") is None
    assert not [c for c in client.calls if c[0] == "odds"]
    assert capsys.readouterr().out.count("Nessun bet id verificato") == 1


async def test_player_card_market_never_uses_bet_11():
    fetcher, client = make_fetcher(load_fixture("odds_player_booked_synthetic.json"))
    await fetcher.get_odds_for_market(900001, "Player Card - Inter Nobody", "Yellow Card")
    assert all(not (c[0] == "odds" and 11 in c[2]) for c in client.calls)


# ── player booked ────────────────────────────────────────────────────────────

def test_parse_booked_value():
    assert parse_booked_value("Lautaro Martínez - Yes") == ("Lautaro Martínez", True)
    assert parse_booked_value("Lautaro Martínez - No") == ("Lautaro Martínez", False)
    assert parse_booked_value("Federico Dimarco") == ("Federico Dimarco", True)
    assert parse_booked_value("Yes") is None


async def test_player_booked_priority_and_no_provider_mixing():
    fetcher, _ = make_fetcher(load_fixture("odds_player_booked_synthetic.json"))
    quotes = await fetcher.get_player_booked_odds(900001)
    lautaro = quotes[normalize_player_name("Lautaro Martinez")]
    assert (lautaro.bookmaker_name, lautaro.odds) == ("Bet365", 4.50)       # not Bwin's 4.75
    assert quotes["stefan de vrij"].bookmaker_name == "Bwin"                 # Bwin beats 1xBet
    assert quotes["hakan calhanoglu"].bookmaker_name == "1xBet"              # only non-priority book
    assert all(q.selection == "Yellow Card" for q in quotes.values())
    assert "lautaro martinez" in quotes and len([k for k in quotes if "martinez" in k]) == 1  # "- No" ignored


async def test_get_odds_for_market_resolves_player_by_initial_and_accent():
    fetcher, _ = make_fetcher(load_fixture("odds_player_booked_synthetic.json"))
    quote = await fetcher.get_odds_for_market(900001, "Player Card - L. Martínez", "Yellow Card")
    assert quote is not None and quote.bookmaker_name == "Bet365" and quote.odds == 4.50
    assert await fetcher.get_odds_for_market(900001, "Player Card - Nobody Here", "Yellow Card") is None


async def test_market_absent_returns_empty_and_is_cached_negatively():
    payload = {"response": []}
    fetcher, client = make_fetcher(payload)
    assert await fetcher.get_player_booked_odds(5) == {}
    assert await fetcher.get_player_booked_odds(5) == {}
    assert len([c for c in client.calls if c[0] == "booked"]) == 1


async def test_api_failure_is_not_cached_and_does_not_raise():
    fetcher, client = make_fetcher(load_fixture("odds_player_booked_synthetic.json"), client_kw={"fail": True})
    assert await fetcher.get_player_booked_odds(1) == {}
    assert await fetcher.get_player_booked_odds(1) == {}
    assert len([c for c in client.calls if c[0] == "booked"]) == 2


async def test_cache_hit_avoids_second_call_and_expires_after_ttl(monkeypatch):
    import core.odds_cache as oc
    now = [1000.0]
    monkeypatch.setattr(oc.time, "time", lambda: now[0])
    fetcher, client = make_fetcher(load_fixture("odds_player_booked_synthetic.json"))
    await fetcher.get_player_booked_odds(900001)
    now[0] += 599
    await fetcher.get_player_booked_odds(900001)
    assert len(client.calls) == 1
    now[0] += 2
    await fetcher.get_player_booked_odds(900001)
    assert len(client.calls) == 2


async def test_redis_raising_never_crashes():
    fetcher, _ = make_fetcher(load_fixture("odds_player_booked_synthetic.json"), redis_cache=DeadRedis())
    assert await fetcher.get_player_booked_odds(900001)
    team_fetcher, _ = make_fetcher(team_payload(), redis_cache=DeadRedis())
    quote = await team_fetcher.get_odds_for_market(1, "Total Cards", "Over 3.5")
    assert quote is not None and quote.bookmaker_name == "Bet365"


async def test_batch_is_capped_at_five_with_pauses(monkeypatch):
    import core.odds_player_booked as opb
    import asyncio
    from core.odds_markets import BATCH_PAUSE_SECONDS
    fetcher, client = make_fetcher(load_fixture("odds_player_booked_synthetic.json"))
    sleeps, in_flight, peak = [], [0], [0]
    real_sleep = asyncio.sleep

    async def fake_sleep(seconds):
        if seconds == BATCH_PAUSE_SECONDS:
            sleeps.append(seconds)
        await real_sleep(0)

    original = fetcher.get_player_booked_odds

    async def tracked(fid):
        in_flight[0] += 1
        peak[0] = max(peak[0], in_flight[0])
        await real_sleep(0)
        result = await original(fid)
        in_flight[0] -= 1
        return result

    monkeypatch.setattr(opb.asyncio, "sleep", lambda s: fake_sleep(s))
    monkeypatch.setattr(fetcher, "get_player_booked_odds", tracked)
    results = await fetcher.get_player_booked_odds_batch(list(range(1, 13)))   # 12 fixtures
    assert len(results) == 12 and peak[0] <= 5
    assert len(sleeps) == 2                                                   # 3 batches -> 2 pauses


def test_no_side_values_never_become_quotes():
    from adapters.odds_api import BookmakerOdds
    book = BookmakerOdds(8, "Bet365", 102, "Player to be booked",
                         [{"value": "Solo No - No", "odd": "1.20"}, {"value": "Both - No", "odd": "1.30"},
                          {"value": "Both - Yes", "odd": "3.00"}])
    quotes = select_player_quotes([book])
    assert "solo no" not in quotes and quotes["both"].odds == 3.00
