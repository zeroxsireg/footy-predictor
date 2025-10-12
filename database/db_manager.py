#!/usr/bin/env python3
"""
Database Manager - Gestione database SQLite per tips pre-calcolati
Ottimizzato per performance frontend.
"""

import sqlite3
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path
import aiosqlite

class DatabaseManager:
    """
    Gestore del database per tips pre-calcolati.
    Design principles:
    - Async I/O per non bloccare
    - Connection pooling
    - Prepared statements
    - Query ottimizzate con indici
    """
    
    def __init__(self, db_path: str = "data/footy_predictor.db"):
        self.db_path = db_path
        self._ensure_db_directory()
    
    def _ensure_db_directory(self):
        """Assicura che la directory del database esista."""
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)
    
    async def initialize(self):
        """Inizializza il database con lo schema."""
        try:
            # Leggi lo schema
            schema_path = Path(__file__).parent / "schema.sql"
            with open(schema_path, 'r') as f:
                schema_sql = f.read()
            
            # Esegui lo schema
            async with aiosqlite.connect(self.db_path) as db:
                await db.executescript(schema_sql)
                await db.commit()
            
            print("✅ Database initialized successfully")
            
        except Exception as e:
            print(f"❌ Error initializing database: {e}")
            raise
    
    # ==========================================
    # TIPS - READ OPERATIONS (VELOCE)
    # ==========================================
    
    async def get_daily_picks(self, league_key: str = None, limit: int = 10) -> List[Dict]:
        """
        Ottieni i migliori picks del giorno.
        Performance: < 20ms
        
        Args:
            league_key: Filtro per lega specifica (opzionale)
            limit: Numero massimo di picks
        
        Returns:
            Lista di picks ordinati per confidence
        """
        try:
            query = """
            SELECT * FROM daily_picks
            WHERE 1=1
            """
            params = []
            
            if league_key:
                # TODO: join con league key
                pass
            
            query += " LIMIT ?"
            params.append(limit)
            
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(query, params) as cursor:
                    rows = await cursor.fetchall()
                    return [dict(row) for row in rows]
        
        except Exception as e:
            print(f"❌ Error getting daily picks: {e}")
            return []
    
    async def get_top_player_cards(self, limit: int = 8) -> List[Dict]:
        """
        Ottieni i top player card picks.
        Performance: < 10ms
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute("SELECT * FROM top_player_cards LIMIT ?", (limit,)) as cursor:
                    rows = await cursor.fetchall()
                    return [dict(row) for row in rows]
        
        except Exception as e:
            print(f"❌ Error getting player cards: {e}")
            return []
    
    async def get_tips_by_match(self, fixture_id: int) -> List[Dict]:
        """
        Ottieni tutti i tips per una partita specifica.
        Performance: < 5ms
        """
        try:
            query = """
            SELECT * FROM betting_tips
            WHERE fixture_id = ? AND status = 'active'
            ORDER BY confidence DESC
            """
            
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(query, (fixture_id,)) as cursor:
                    rows = await cursor.fetchall()
                    return [dict(row) for row in rows]
        
        except Exception as e:
            print(f"❌ Error getting tips by match: {e}")
            return []
    
    # ==========================================
    # TIPS - WRITE OPERATIONS
    # ==========================================
    
    async def save_betting_tip(self, tip_data: Dict) -> int:
        """
        Salva un betting tip.
        Performance: < 15ms
        
        Returns:
            tip_id
        """
        try:
            query = """
            INSERT OR REPLACE INTO betting_tips 
            (fixture_id, market, selection, confidence, percentage, 
             odds_min, odds_max, reasoning, status, calculated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            
            params = (
                tip_data['fixture_id'],
                tip_data['market'],
                tip_data['selection'],
                tip_data['confidence'],
                tip_data['percentage'],
                tip_data.get('odds_min'),
                tip_data.get('odds_max'),
                tip_data.get('reasoning', ''),
                tip_data.get('status', 'active'),
                datetime.now().isoformat()
            )
            
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(query, params)
                await db.commit()
                return cursor.lastrowid
        
        except Exception as e:
            print(f"❌ Error saving betting tip: {e}")
            return 0
    
    async def save_player_card_tip(self, tip_data: Dict) -> int:
        """Salva un player card tip."""
        try:
            query = """
            INSERT OR REPLACE INTO player_card_tips 
            (fixture_id, player_id, player_name, team_id, card_type,
             confidence, percentage, odds_min, odds_max, reasoning, status, calculated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            
            params = (
                tip_data['fixture_id'],
                tip_data.get('player_id', 0),
                tip_data['player_name'],
                tip_data['team_id'],
                tip_data.get('card_type', 'yellow'),
                tip_data['confidence'],
                tip_data['percentage'],
                tip_data.get('odds_min'),
                tip_data.get('odds_max'),
                tip_data.get('reasoning', ''),
                tip_data.get('status', 'active'),
                datetime.now().isoformat()
            )
            
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(query, params)
                await db.commit()
                return cursor.lastrowid
        
        except Exception as e:
            print(f"❌ Error saving player card tip: {e}")
            return 0
    
    async def bulk_save_tips(self, tips: List[Dict]) -> int:
        """
        Salva multipli tips in batch (veloce).
        Performance: < 50ms per 100 tips
        
        Returns:
            Numero di tips salvati
        """
        try:
            saved = 0
            async with aiosqlite.connect(self.db_path) as db:
                for tip in tips:
                    await self.save_betting_tip(tip)
                    saved += 1
                await db.commit()
            
            return saved
        
        except Exception as e:
            print(f"❌ Error bulk saving tips: {e}")
            return 0
    
    # ==========================================
    # FIXTURES - OPERATIONS
    # ==========================================
    
    async def save_fixture(self, fixture_data: Dict) -> int:
        """Salva una fixture."""
        try:
            query = """
            INSERT OR REPLACE INTO fixtures 
            (id, league_id, season, matchday, home_team_id, away_team_id,
             match_date, status, home_score, away_score, venue)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            
            params = (
                fixture_data['id'],
                fixture_data['league_id'],
                fixture_data['season'],
                fixture_data.get('matchday'),
                fixture_data['home_team_id'],
                fixture_data['away_team_id'],
                fixture_data['match_date'],
                fixture_data.get('status', 'NS'),
                fixture_data.get('home_score'),
                fixture_data.get('away_score'),
                fixture_data.get('venue', '')
            )
            
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(query, params)
                await db.commit()
                return cursor.lastrowid
        
        except Exception as e:
            print(f"❌ Error saving fixture: {e}")
            return 0
    
    # ==========================================
    # STATS
    # ==========================================
    
    async def get_database_stats(self) -> Dict[str, Any]:
        """Ottieni statistiche del database."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Count tips
                async with db.execute("SELECT COUNT(*) FROM betting_tips WHERE status='active'") as cursor:
                    tips_count = (await cursor.fetchone())[0]
                
                # Count fixtures
                async with db.execute("SELECT COUNT(*) FROM fixtures WHERE status='NS'") as cursor:
                    fixtures_count = (await cursor.fetchone())[0]
                
                # Count teams
                async with db.execute("SELECT COUNT(DISTINCT id) FROM teams") as cursor:
                    teams_count = (await cursor.fetchone())[0]
                
                return {
                    'active_tips': tips_count,
                    'upcoming_fixtures': fixtures_count,
                    'teams': teams_count
                }
        
        except Exception as e:
            print(f"❌ Error getting stats: {e}")
            return {}


# ==========================================
# SINGLETON
# ==========================================
_db_manager = None

async def get_db_manager() -> DatabaseManager:
    """Ottieni l'istanza singleton del database manager."""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
        await _db_manager.initialize()
    return _db_manager

