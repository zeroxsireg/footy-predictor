"""Configuration management for the footy predictor CLI."""

from pydantic_settings import BaseSettings
from typing import Optional, List


class Settings(BaseSettings):
    """Application settings."""
    
    api_football_key: str
    api_football_base: str = "https://v3.football.api-sports.io"
    default_country: str = "Italy"
    default_league: str = "Serie A"
    default_season: int = 2025
    
    # Redis Configuration
    redis_host: str
    redis_port: int = 6379
    redis_password: str
    redis_ssl: bool = True
    redis_db: int = 0
    
    # Preferred bookmaker for odds (Bet365 only)
    preferred_bookmakers: List[int] = [8]  # Bet365 only
    primary_bookmaker: int = 8  # Bet365
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


def get_settings() -> Settings:
    """Get application settings."""
    return Settings()
