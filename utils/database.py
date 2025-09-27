"""Database utilities for caching shots and corners statistics."""

import sqlite3
import os
from datetime import datetime
from typing import Dict, Optional, Tuple
from pathlib import Path


class ShotsCornerCache:
    """SQLite database cache for shots and corners statistics."""
    
    def __init__(self, db_path: str = "shots_corners_cache.db"):
        """Initialize the database cache."""
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """Initialize the database tables."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Table for team statistics
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS team_stats (
                    team_id INTEGER,
                    league_id INTEGER,
                    season INTEGER,
                    shots_total INTEGER DEFAULT 0,
                    shots_on_target INTEGER DEFAULT 0,
                    corners INTEGER DEFAULT 0,
                    matches_processed INTEGER DEFAULT 0,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (team_id, league_id, season)
                )
            """)
            
            # Table for processed matches (to avoid reprocessing)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS processed_matches (
                    match_id INTEGER PRIMARY KEY,
                    team_id INTEGER,
                    league_id INTEGER,
                    season INTEGER,
                    processed_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Table for league season completion status
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS league_seasons (
                    league_id INTEGER,
                    season INTEGER,
                    is_completed BOOLEAN DEFAULT FALSE,
                    last_check TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (league_id, season)
                )
            """)
            
            conn.commit()
    
    def get_team_stats(self, team_id: int, league_id: int, season: int) -> Optional[Dict[str, int]]:
        """Get cached team statistics."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT shots_total, shots_on_target, corners, matches_processed, last_updated
                FROM team_stats 
                WHERE team_id = ? AND league_id = ? AND season = ?
            """, (team_id, league_id, season))
            
            result = cursor.fetchone()
            if result:
                return {
                    "shots_total": result[0],
                    "shots_on_target": result[1], 
                    "corners": result[2],
                    "matches_processed": result[3],
                    "last_updated": result[4]
                }
            return None
    
    def save_team_stats(self, team_id: int, league_id: int, season: int, 
                       shots_total: int, shots_on_target: int, corners: int, 
                       matches_processed: int):
        """Save team statistics to cache."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO team_stats 
                (team_id, league_id, season, shots_total, shots_on_target, corners, matches_processed, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (team_id, league_id, season, shots_total, shots_on_target, corners, matches_processed))
            conn.commit()
    
    def is_match_processed(self, match_id: int) -> bool:
        """Check if a match has been processed."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM processed_matches WHERE match_id = ?", (match_id,))
            return cursor.fetchone() is not None
    
    def mark_match_processed(self, match_id: int, team_id: int, league_id: int, season: int):
        """Mark a match as processed."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR IGNORE INTO processed_matches 
                (match_id, team_id, league_id, season)
                VALUES (?, ?, ?, ?)
            """, (match_id, team_id, league_id, season))
            conn.commit()
    
    def is_season_completed(self, league_id: int, season: int) -> bool:
        """Check if a season is marked as completed."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT is_completed FROM league_seasons 
                WHERE league_id = ? AND season = ?
            """, (league_id, season))
            
            result = cursor.fetchone()
            return result and result[0]
    
    def mark_season_completed(self, league_id: int, season: int):
        """Mark a season as completed."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO league_seasons 
                (league_id, season, is_completed, last_check)
                VALUES (?, ?, TRUE, CURRENT_TIMESTAMP)
            """, (league_id, season))
            conn.commit()
    
    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM team_stats")
            teams_cached = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM processed_matches")
            matches_processed = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM league_seasons WHERE is_completed = TRUE")
            seasons_completed = cursor.fetchone()[0]
            
            return {
                "teams_cached": teams_cached,
                "matches_processed": matches_processed,
                "seasons_completed": seasons_completed
            }
    
    def clear_cache(self):
        """Clear all cache data."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM team_stats")
            cursor.execute("DELETE FROM processed_matches")
            cursor.execute("DELETE FROM league_seasons")
            conn.commit()
    
    def cleanup_old_data(self, days_old: int = 30):
        """Remove cache data older than specified days."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM team_stats 
                WHERE last_updated < datetime('now', '-{} days')
            """.format(days_old))
            
            cursor.execute("""
                DELETE FROM processed_matches 
                WHERE processed_date < datetime('now', '-{} days')
            """.format(days_old))
            
            conn.commit()
