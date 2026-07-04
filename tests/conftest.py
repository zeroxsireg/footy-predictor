"""Shared pytest fixtures and factories for the footy-predictor test suite."""

import pytest

from core.models import Team, TeamStats


def make_team(name: str = "Test FC", team_id: int = 1) -> Team:
    """Build a minimal Team."""
    return Team(id=team_id, name=name)


def make_team_stats(
    name: str = "Test FC",
    team_id: int = 1,
    *,
    matches_played: int = 10,
    goals_for: int = 15,
    goals_against: int = 10,
    clean_sheets: int = 3,
    failed_to_score: int = 2,
    yellow_cards: int = 20,
    corners: int = 55,
    shots_total: int = 120,
    shots_on_target: int = 45,
    **overrides,
) -> TeamStats:
    """
    Build a TeamStats with sensible defaults.

    Every field the analyzers read is populated; pass keyword overrides to
    shape a specific scenario (e.g. goals_for=30 for a high-scoring side).
    """
    stats = TeamStats(
        team=make_team(name, team_id),
        matches_played=matches_played,
        wins=5,
        draws=2,
        losses=3,
        goals_for=goals_for,
        goals_against=goals_against,
        shots_total=shots_total,
        shots_on_target=shots_on_target,
        corners=corners,
        yellow_cards=yellow_cards,
        red_cards=1,
        clean_sheets=clean_sheets,
        failed_to_score=failed_to_score,
    )
    for key, value in overrides.items():
        setattr(stats, key, value)
    return stats


@pytest.fixture
def team_stats_factory():
    """Expose the factory to tests that need custom-shaped teams."""
    return make_team_stats


@pytest.fixture
def high_scoring_home():
    """A prolific home side: ~2.5 goals/game, leaky defence."""
    return make_team_stats(
        "Attackers United", 10,
        goals_for=25, goals_against=15, clean_sheets=1, failed_to_score=0,
    )


@pytest.fixture
def high_scoring_away():
    """A prolific away side: ~2.0 goals/game, leaky defence."""
    return make_team_stats(
        "Goal Machine", 20,
        goals_for=20, goals_against=14, clean_sheets=1, failed_to_score=1,
    )


@pytest.fixture
def low_scoring_home():
    """A defensive, low-scoring home side: ~0.5 goals/game."""
    return make_team_stats(
        "Catenaccio FC", 30,
        goals_for=5, goals_against=4, clean_sheets=6, failed_to_score=6,
    )


@pytest.fixture
def low_scoring_away():
    """A defensive, low-scoring away side: ~0.5 goals/game."""
    return make_team_stats(
        "Park The Bus", 40,
        goals_for=4, goals_against=5, clean_sheets=5, failed_to_score=6,
    )
