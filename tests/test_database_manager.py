"""
Tests for DatabaseManager and consolidated SQLite schema.

Ensures schema initialization, WAL configuration, betting tips, fixtures,
and player history query functionality on ephemeral in-memory SQLite instances.
Conforms strictly to Rule 1 (.agents/GEMINI.md): never touch production DBs.
"""

import pytest
import pytest_asyncio
import aiosqlite
from pathlib import Path
from database.db_manager import DatabaseManager


@pytest_asyncio.fixture
async def memory_db():
    """Create an initialized in-memory database instance."""
    db = DatabaseManager(db_path=":memory:")
    await db.initialize()
    yield db
    await db.close()


@pytest.mark.asyncio
async def test_database_initialization(memory_db):
    """Test that all tables and views are initialized properly."""
    async with memory_db.connect() as conn:
        async with conn.execute("SELECT name, type FROM sqlite_master WHERE type IN ('table', 'view')") as cursor:
            rows = await cursor.fetchall()
            names = {r["name"] for r in rows}

    assert "leagues" in names
    assert "teams" in names
    assert "fixtures" in names
    assert "betting_tips" in names
    assert "player_card_tips" in names
    assert "player_history" in names
    assert "daily_picks" in names
    assert "top_player_cards" in names


@pytest.mark.asyncio
async def test_save_and_retrieve_fixture(memory_db):
    """Test saving a fixture and reading it back."""
    # First insert prerequisite league and teams
    async with memory_db.connect() as conn:
        await conn.execute(
            "INSERT INTO leagues (id, key, name, country, country_code, flag, api_league_id) "
            "VALUES (135, 'serie_a', 'Serie A', 'Italy', 'IT', '🇮🇹', 135)"
        )
        await conn.execute(
            "INSERT INTO teams (id, name, league_id, season) VALUES (505, 'Inter', 135, 2026)"
        )
        await conn.execute(
            "INSERT INTO teams (id, name, league_id, season) VALUES (492, 'Napoli', 135, 2026)"
        )
        await conn.commit()

    fixture_data = {
        "id": 99901,
        "league_id": 135,
        "season": 2026,
        "matchday": 5,
        "home_team_id": 505,
        "away_team_id": 492,
        "match_date": "2026-10-01 20:45:00",
        "status": "NS",
        "venue": "San Siro",
    }
    fid = await memory_db.save_fixture(fixture_data)
    assert fid > 0

    stats = await memory_db.get_database_stats()
    assert stats["upcoming_fixtures"] == 1
    assert stats["teams"] == 2


@pytest.mark.asyncio
async def test_save_and_retrieve_betting_tip(memory_db):
    """Test saving betting tips and retrieving tips by match."""
    # Insert prerequisite league, teams and fixture
    async with memory_db.connect() as conn:
        await conn.execute(
            "INSERT INTO leagues (id, key, name, country, country_code, flag, api_league_id) "
            "VALUES (135, 'serie_a', 'Serie A', 'Italy', 'IT', '🇮🇹', 135)"
        )
        await conn.execute(
            "INSERT INTO teams (id, name, league_id, season) VALUES (505, 'Inter', 135, 2026)"
        )
        await conn.execute(
            "INSERT INTO teams (id, name, league_id, season) VALUES (492, 'Napoli', 135, 2026)"
        )
        await conn.execute(
            "INSERT INTO fixtures (id, league_id, season, home_team_id, away_team_id, match_date, status) "
            "VALUES (1001, 135, 2026, 505, 492, datetime('now', '+2 days'), 'NS')"
        )
        await conn.commit()

    tip = {
        "fixture_id": 1001,
        "market": "Match Result",
        "selection": "Home Win",
        "confidence": 0.65,
        "percentage": 65.0,
        "odds_min": 1.90,
        "odds_max": 2.05,
        "reasoning": "Strong home form",
        "status": "active",
    }
    saved_id = await memory_db.save_betting_tip(tip)
    assert saved_id > 0

    tips = await memory_db.get_tips_by_match(1001)
    assert len(tips) == 1
    assert tips[0]["selection"] == "Home Win"
    assert tips[0]["confidence"] == 0.65

    # Check daily_picks view
    daily = await memory_db.get_daily_picks(limit=5)
    assert len(daily) == 1
    assert daily[0]["home_team"] == "Inter"
    assert daily[0]["away_team"] == "Napoli"


@pytest.mark.asyncio
async def test_player_history_operations(memory_db):
    """Test inserting and querying player historical records."""
    records = [
        {
            "player_name": "Nicolo Barella",
            "team_name": "Inter",
            "league": "Serie A",
            "season": 2025,
            "appearances": 34,
            "minutes_played": 2800,
            "yellow_cards": 7,
            "red_cards": 0,
            "fouls_committed": 42,
            "position": "Midfielder",
        },
        {
            "player_name": "Nicolo Barella",
            "team_name": "Inter",
            "league": "Serie A",
            "season": 2024,
            "appearances": 32,
            "minutes_played": 2650,
            "yellow_cards": 6,
            "red_cards": 1,
            "fouls_committed": 38,
            "position": "Midfielder",
        },
        {
            "player_name": "Lautaro Martinez",
            "team_name": "Inter",
            "league": "Serie A",
            "season": 2025,
            "appearances": 35,
            "minutes_played": 2900,
            "yellow_cards": 3,
            "red_cards": 0,
            "fouls_committed": 25,
            "position": "Forward",
        },
    ]

    for rec in records:
        await memory_db.save_player_history(rec)

    # Test single player lookup
    barella_history = await memory_db.get_player_history("Nicolo Barella", seasons=2)
    assert len(barella_history) == 2
    assert barella_history[0]["season"] == 2025
    assert barella_history[0]["yellow_cards"] == 7
    assert barella_history[1]["season"] == 2024

    # Test team top cards
    inter_cards = await memory_db.get_team_top_cards("Inter", season=2025, limit=5)
    assert len(inter_cards) == 2
    # Barella has 7 yellows, Lautaro has 3 -> Barella should be first
    assert inter_cards[0]["player_name"] == "Nicolo Barella"
    assert inter_cards[1]["player_name"] == "Lautaro Martinez"

    # Test database stats
    stats = await memory_db.get_database_stats()
    assert stats["player_history_records"] == 3
