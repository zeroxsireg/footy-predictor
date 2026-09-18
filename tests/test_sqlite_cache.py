"""Cache SQLite: SOLO sqlite :memory: (mai data/footy_predictor.db), nessuna rete."""

import types
from datetime import datetime, timedelta, timezone

import pytest

from database.db_manager import DatabaseManager
from utils import cache_manager
from utils.sqlite_cache import SqliteFootballCache

T0 = datetime(2026, 9, 18, 12, 0, 0, tzinfo=timezone.utc)


class Clock:
    def __init__(self):
        self.now = T0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now = self.now + timedelta(seconds=seconds)


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def cache(clock):
    c = SqliteFootballCache(":memory:", clock=clock)
    yield c
    c.close()


def raw_row(cache, key):
    return cache._conn.execute("SELECT value, expires_at, ttl_type FROM api_cache WHERE key = ?", (key,)).fetchone()


# ── core ─────────────────────────────────────────────────────────────────────

async def test_set_get_roundtrip_and_hit_counter(cache):
    assert cache.is_connected() is True
    assert await cache.set_data("k", {"a": [1, 2], "b": "è"}, "live_odds") is True
    assert await cache.get_data("k") == {"a": [1, 2], "b": "è"}
    assert cache.stats["hits"] == 1 and cache.stats["writes"] == 1


async def test_miss_returns_none_and_counts(cache):
    assert await cache.get_data("absent") is None
    assert cache.stats["misses"] == 1 and cache.stats["hits"] == 0


async def test_overwrite_replaces_value(cache):
    await cache.set_data("k", 1, "live_odds")
    await cache.set_data("k", 2, "live_odds")
    assert await cache.get_data("k") == 2
    assert cache._conn.execute("SELECT COUNT(*) FROM api_cache").fetchone()[0] == 1


async def test_ttl_expired_is_miss_and_row_deleted(cache, clock):
    await cache.set_data("k", "v", "live_odds")          # 1800 s
    clock.advance(1799)
    assert await cache.get_data("k") == "v"
    clock.advance(2)
    assert await cache.get_data("k") is None
    assert raw_row(cache, "k") is None
    assert cache.stats["expired"] == 1


async def test_ttl_minus_one_never_expires(cache, clock):
    await cache.set_data("k", "v", "team_stats")          # -1
    assert raw_row(cache, "k")[1] is None
    clock.advance(10 * 365 * 24 * 3600)
    assert await cache.get_data("k") == "v"


async def test_unknown_ttl_type_defaults_to_one_hour(cache, clock):
    await cache.set_data("k", "v", "no_such_type")
    clock.advance(3599)
    assert await cache.get_data("k") == "v"
    clock.advance(2)
    assert await cache.get_data("k") is None


async def test_cleanup_removes_only_expired(cache, clock):
    await cache.set_data("short", 1, "live_odds")
    await cache.set_data("perm", 2, "team_stats")
    await cache.set_data("day", 3, "league_standings")
    clock.advance(1801)
    assert cache.cache_cleanup_expired() == 1
    assert raw_row(cache, "short") is None
    assert raw_row(cache, "perm") is not None and raw_row(cache, "day") is not None


async def test_compression_only_for_large_payloads(cache):
    big = [{"name": f"Player {i}", "yellow": i} for i in range(200)]
    await cache.set_data("big", big, "roster")
    await cache.set_data("small", {"x": 1}, "roster")
    assert raw_row(cache, "big")[0].startswith("gz:")
    assert raw_row(cache, "small")[0].startswith("js:")
    assert await cache.get_data("big") == big


async def test_corrupt_value_is_a_miss_not_a_crash(cache):
    cache._conn.execute("INSERT INTO api_cache (key, value) VALUES ('bad', 'gz:%%%')")
    assert await cache.get_data("bad") is None


async def test_clear_all_and_sample_keys_and_info(cache):
    await cache.set_data("a", 1, "live_odds")
    await cache.set_data("b", 2, "live_odds")
    assert sorted(await cache.get_sample_keys(10)) == ["a", "b"]
    info = await cache.get_cache_info()
    assert info["total_keys"] == 2 and info["backend"] == "sqlite"
    await cache.clear_all_cache()
    assert await cache.get_sample_keys() == []


def test_health_check_and_memory_usage(cache):
    health = cache.health_check()
    assert health["status"] == "healthy" and health["backend"] == "sqlite"
    assert health["memory_usage"]["keys_count"] == 0 and "used_memory_human" in health["memory_usage"]


# ── fallback ─────────────────────────────────────────────────────────────────

async def test_closed_backend_degrades_without_raising(cache):
    cache.close()
    assert cache.is_connected() is False
    assert await cache.get_data("k") is None
    assert await cache.set_data("k", 1, "live_odds") is False
    assert cache.get_team_roster(1, 2026) is None
    assert cache.get_cached_teams(2026) == []
    assert cache.health_check()["status"] == "disconnected"


def test_unopenable_path_yields_disconnected_cache(tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("x")
    broken = SqliteFootballCache(str(blocker / "sub" / "cache.db"))   # parent is a file
    assert broken.is_connected() is False
    assert broken.get_team_roster(1, 2026) is None


# ── signature preservate ─────────────────────────────────────────────────────

def test_roster_signature(cache):
    roster = [{"name": "A", "yellow_cards": 2}]
    assert cache.get_team_roster(505, 2026) is None
    assert cache.set_team_roster(505, 2026, roster) is True
    assert cache.get_team_roster(505, 2026) == roster
    assert cache.get_team_roster(505, 2025) is None


def test_roster_ttl_type_override_expires_after_24h(cache, clock):
    cache.set_team_roster(505, 2026, [{"n": 1}], ttl_type="league_players_all")
    clock.advance(24 * 3600 - 1)
    assert cache.get_team_roster(505, 2026) == [{"n": 1}]
    clock.advance(2)
    assert cache.get_team_roster(505, 2026) is None


def test_shots_corners_signature_adds_metadata(cache):
    assert cache.set_team_shots_corners(505, 2026, {"corners": 55}) is True
    got = cache.get_team_shots_corners(505, 2026)
    assert got["corners"] == 55 and got["_metadata"]["team_id"] == 505
    assert cache.is_historical_data(got) is True
    assert raw_row(cache, "team:505:2026:shots_corners")[1] is None      # permanente


def test_team_stats_and_match_stats_signatures(cache):
    cache.set_team_stats(505, 135, 2026, {"goals": 9})
    assert cache.get_team_stats(505, 135, 2026)["goals"] == 9
    cache.set_match_stats(77, {"shots": 3})
    assert cache.get_match_stats(77) == {"shots": 3}


def test_cached_teams_lists_only_rosters_of_that_season(cache, clock):
    cache.set_team_roster(505, 2026, [{"a": 1}])
    cache.set_team_roster(496, 2026, [{"a": 1}])
    cache.set_team_roster(489, 2025, [{"a": 1}])
    cache.set_team_shots_corners(499, 2026, {"corners": 1})       # not a roster
    assert sorted(cache.get_cached_teams(2026)) == ["496", "505"]
    assert cache.get_cached_teams(2025) == ["489"]
    clock.advance(31 * 24 * 3600)                                   # roster TTL 30d -> gone
    assert cache.get_cached_teams(2026) == []


def test_clear_team_cache_scopes_to_team_and_season(cache):
    cache.set_team_roster(505, 2026, [1])
    cache.set_team_roster(505, 2025, [1])
    cache.set_team_stats(505, 135, 2026, {"g": 1})
    cache.set_team_roster(496, 2026, [1])
    cache.clear_team_cache(505, 2026)
    assert cache.get_team_roster(505, 2026) is None and cache.get_team_stats(505, 135, 2026) is None
    assert cache.get_team_roster(505, 2025) == [1] and cache.get_team_roster(496, 2026) == [1]


# ── DatabaseManager helpers (aiosqlite :memory:) ─────────────────────────────

async def test_database_manager_cache_helpers(clock):
    db = DatabaseManager(":memory:")
    await db.initialize()
    try:
        await db.cache_set("k", "v", ttl_type="live_odds", now=T0)
        assert await db.cache_get("k", now=T0) == "v"
        assert await db.cache_get("k", now=T0 + timedelta(seconds=1801)) is None     # scaduta + eliminata
        assert await db.cache_get("k", now=T0) is None
        await db.cache_set("p", "v", ttl_type="team_stats", now=T0)                  # -1
        await db.cache_set("s", "v", ttl_seconds=10, now=T0)
        await db.cache_set("z", "v", ttl_seconds=0, now=T0)                          # 0 = permanente
        assert await db.cache_cleanup_expired(now=T0 + timedelta(days=3650)) == 1
        assert await db.cache_get("z", now=T0 + timedelta(days=3650)) == "v"
        assert await db.cache_get("p", now=T0 + timedelta(days=3650)) == "v"
        assert await db.cache_delete("p") is True and await db.cache_delete("p") is False
    finally:
        await db.close()


# ── selettore backend e config ───────────────────────────────────────────────

def test_settings_need_no_redis_variables(monkeypatch):
    from core.config import Settings
    for var in ("REDIS_HOST", "REDIS_PASSWORD", "CACHE_BACKEND"):
        monkeypatch.delenv(var, raising=False)
    settings = Settings(_env_file=None, api_football_key="k")
    assert settings.cache_backend == "sqlite" and settings.redis_host == ""


def test_build_cache_sqlite_default_and_auto_without_redis_prints_once(capsys):
    cache_manager.reset_cache()
    first = cache_manager.build_cache("sqlite", ":memory:")
    assert isinstance(first, SqliteFootballCache) and capsys.readouterr().out == ""
    a = cache_manager.build_cache("auto", ":memory:", redis_host="")
    b = cache_manager.build_cache("redis", ":memory:", redis_host="")
    assert isinstance(a, SqliteFootballCache) and isinstance(b, SqliteFootballCache)
    assert capsys.readouterr().out.count("Redis non raggiungibile") == 1
    cache_manager.reset_cache()


# ── rose: il fallback API persiste sulla cache ───────────────────────────────

async def test_roster_fallback_persists_to_sqlite_for_24h(cache, clock):
    from adapters.roster_fallback import clear_roster_memory, get_team_roster_with_fallback
    from tests.odds_helpers import load_fixture
    from tests.test_roster_fallback import FakeHTTP

    clear_roster_memory()
    http = FakeHTTP(pages=[load_fixture("players_team_505_page1.json")["response"]])
    api = types.SimpleNamespace(redis_cache=cache, _http=http)
    roster = await get_team_roster_with_fallback(api, 505, 2026)
    assert roster and cache.get_team_roster(505, 2026) == roster
    clock.advance(24 * 3600 + 1)
    assert cache.get_team_roster(505, 2026) is None
    clear_roster_memory()
