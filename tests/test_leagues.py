"""Tests for config.leagues — the LeagueManager and its singleton accessor."""

from config.leagues import LeagueManager, LeagueConfig, get_league_manager


def test_singleton_returns_same_instance():
    assert get_league_manager() is get_league_manager()


def test_enabled_leagues_are_a_subset_of_all():
    mgr = LeagueManager()
    enabled = mgr.get_enabled_leagues()
    all_leagues = mgr.get_all_leagues()
    assert set(l.key for l in enabled) <= set(l.key for l in all_leagues)
    assert all(l.enabled for l in enabled)


def test_enabled_leagues_sorted_by_priority():
    enabled = LeagueManager().get_enabled_leagues()
    priorities = [l.priority for l in enabled]
    assert priorities == sorted(priorities)


def test_enable_and_disable_toggle_state():
    mgr = LeagueManager()
    mgr.disable_league("serie_a")
    assert mgr.get_league("serie_a").enabled is False
    assert "serie_a" not in {l.key for l in mgr.get_enabled_leagues()}

    mgr.enable_league("serie_a")
    assert mgr.get_league("serie_a").enabled is True
    assert "serie_a" in {l.key for l in mgr.get_enabled_leagues()}


def test_get_unknown_league_returns_none():
    assert LeagueManager().get_league("does_not_exist") is None


def test_add_league_registers_new_entry():
    mgr = LeagueManager()
    mgr.add_league(LeagueConfig(
        key="mls", name="MLS", country="USA", country_code="US",
        flag="🇺🇸", api_league_id=253, enabled=True, priority=99,
    ))
    assert mgr.get_league("mls").name == "MLS"
    assert "mls" in {l.key for l in mgr.get_enabled_leagues()}


def test_toggle_on_fresh_manager_does_not_leak_into_singleton():
    # Mutating a locally-built manager must not affect the shared singleton.
    local = LeagueManager()
    local.disable_league("serie_a")
    # A fresh instance still reflects the module defaults.
    assert LeagueManager().get_league("serie_a").enabled is True
