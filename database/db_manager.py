#!/usr/bin/env python3
"""
Database Manager - Gestione database SQLite con WAL mode.

Ottimizzato per performance sub-millisecond, query indicizzate e concorrenza.
"""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any
import aiosqlite

from database import cache_sql
from utils import cache_ttl


class DatabaseManager:
    """Gestore asincrono del database SQLite per tips, fixtures e player history."""

    def __init__(self, db_path: str = "data/footy_predictor.db"):
        self.db_path = db_path
        self._mem_conn = None
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

    @asynccontextmanager
    async def connect(self):
        """Generatore di connessione asincrono con PRAGMAs WAL attivi."""
        if self.db_path == ":memory:":
            if self._mem_conn is None:
                self._mem_conn = await aiosqlite.connect(":memory:")
                self._mem_conn.row_factory = aiosqlite.Row
                await self._mem_conn.execute("PRAGMA synchronous = NORMAL;")
                await self._mem_conn.execute("PRAGMA foreign_keys = ON;")
            yield self._mem_conn
        else:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                await db.execute("PRAGMA journal_mode = WAL;")
                await db.execute("PRAGMA synchronous = NORMAL;")
                await db.execute("PRAGMA foreign_keys = ON;")
                yield db

    async def initialize(self):
        """Inizializza lo schema del database da schema.sql."""
        schema_path = Path(__file__).parent / "schema.sql"
        with open(schema_path, "r", encoding="utf-8") as f:
            schema_sql = f.read()

        async with self.connect() as db:
            await db.executescript(schema_sql)
            await db.commit()

    async def close(self):
        """Chiude la connessione permanente se attiva."""
        if self._mem_conn:
            await self._mem_conn.close()
            self._mem_conn = None

    async def get_daily_picks(self, league_key: Optional[str] = None, limit: int = 10) -> List[Dict]:
        """Ottieni i migliori picks del giorno."""
        try:
            async with self.connect() as db:
                async with db.execute("SELECT * FROM daily_picks LIMIT ?", (limit,)) as cursor:
                    return [dict(r) for r in await cursor.fetchall()]
        except Exception:
            return []

    async def get_top_player_cards(self, limit: int = 8) -> List[Dict]:
        """Ottieni i top player card picks."""
        try:
            async with self.connect() as db:
                async with db.execute("SELECT * FROM top_player_cards LIMIT ?", (limit,)) as cursor:
                    return [dict(r) for r in await cursor.fetchall()]
        except Exception:
            return []

    async def get_tips_by_match(self, fixture_id: int) -> List[Dict]:
        """Ottieni tutti i tips attivi per una partita specifica."""
        try:
            q = "SELECT * FROM betting_tips WHERE fixture_id = ? AND status = 'active' ORDER BY confidence DESC"
            async with self.connect() as db:
                async with db.execute(q, (fixture_id,)) as cursor:
                    return [dict(r) for r in await cursor.fetchall()]
        except Exception:
            return []

    async def save_betting_tip(self, t: Dict) -> int:
        """Salva o aggiorna un betting tip."""
        try:
            q = """INSERT OR REPLACE INTO betting_tips
                   (fixture_id, market, selection, confidence, percentage,
                    odds_min, odds_max, reasoning, status, calculated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""
            params = (
                t["fixture_id"], t["market"], t["selection"], t["confidence"], t["percentage"],
                t.get("odds_min"), t.get("odds_max"), t.get("reasoning", ""),
                t.get("status", "active"), datetime.now().isoformat()
            )
            async with self.connect() as db:
                cursor = await db.execute(q, params)
                await db.commit()
                return cursor.lastrowid or 0
        except Exception:
            return 0

    async def save_player_card_tip(self, t: Dict) -> int:
        """Salva o aggiorna un player card tip."""
        try:
            q = """INSERT OR REPLACE INTO player_card_tips
                   (fixture_id, player_id, player_name, team_id, card_type,
                    confidence, percentage, odds_min, odds_max, reasoning, status, calculated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""
            params = (
                t["fixture_id"], t.get("player_id", 0), t["player_name"], t["team_id"],
                t.get("card_type", "yellow"), t["confidence"], t["percentage"],
                t.get("odds_min"), t.get("odds_max"), t.get("reasoning", ""),
                t.get("status", "active"), datetime.now().isoformat()
            )
            async with self.connect() as db:
                cursor = await db.execute(q, params)
                await db.commit()
                return cursor.lastrowid or 0
        except Exception:
            return 0

    async def bulk_save_tips(self, tips: List[Dict]) -> int:
        """Salva multipli tips in batch."""
        saved = 0
        for tip in tips:
            if await self.save_betting_tip(tip):
                saved += 1
        return saved

    async def save_fixture(self, f: Dict) -> int:
        """Salva o aggiorna una fixture."""
        try:
            q = """INSERT OR REPLACE INTO fixtures
                   (id, league_id, season, matchday, home_team_id, away_team_id,
                    match_date, status, home_score, away_score, venue)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""
            params = (
                f["id"], f["league_id"], f["season"], f.get("matchday"),
                f["home_team_id"], f["away_team_id"], f["match_date"],
                f.get("status", "NS"), f.get("home_score"), f.get("away_score"), f.get("venue", "")
            )
            async with self.connect() as db:
                cursor = await db.execute(q, params)
                await db.commit()
                return cursor.lastrowid or 0
        except Exception:
            return 0

    async def save_player_history(self, p: Dict) -> int:
        """Salva record storico del calciatore."""
        try:
            q = """INSERT OR REPLACE INTO player_history
                   (player_name, team_name, league, season, appearances, minutes_played,
                    yellow_cards, red_cards, fouls_committed, position)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""
            params = (
                p["player_name"], p["team_name"], p.get("league", ""), p["season"],
                p.get("appearances", 0), p.get("minutes_played", 0),
                p.get("yellow_cards", 0), p.get("red_cards", 0),
                p.get("fouls_committed", 0), p.get("position", "")
            )
            async with self.connect() as db:
                cursor = await db.execute(q, params)
                await db.commit()
                return cursor.lastrowid or 0
        except Exception:
            return 0

    async def get_player_history(self, player_name: str, seasons: int = 2) -> List[Dict]:
        """Recupera le ultime N stagioni di un giocatore."""
        try:
            q = "SELECT * FROM player_history WHERE player_name = ? ORDER BY season DESC LIMIT ?"
            async with self.connect() as db:
                async with db.execute(q, (player_name, seasons)) as cursor:
                    return [dict(r) for r in await cursor.fetchall()]
        except Exception:
            return []

    async def get_team_top_cards(self, team_name: str, season: int, limit: int = 6) -> List[Dict]:
        """Recupera i giocatori con più cartellini per una squadra in una stagione."""
        try:
            q = """SELECT * FROM player_history
                   WHERE team_name = ? AND season = ?
                   ORDER BY yellow_cards DESC, red_cards DESC LIMIT ?"""
            async with self.connect() as db:
                async with db.execute(q, (team_name, season, limit)) as cursor:
                    return [dict(r) for r in await cursor.fetchall()]
        except Exception:
            return []

    async def get_database_stats(self) -> Dict[str, Any]:
        """Ottieni statistiche sintetiche del database."""
        try:
            async with self.connect() as db:
                async with db.execute("SELECT COUNT(*) FROM betting_tips WHERE status='active'") as cur:
                    tips = (await cur.fetchone())[0]
                async with db.execute("SELECT COUNT(*) FROM fixtures WHERE status='NS'") as cur:
                    fixtures = (await cur.fetchone())[0]
                async with db.execute("SELECT COUNT(DISTINCT id) FROM teams") as cur:
                    teams = (await cur.fetchone())[0]
                async with db.execute("SELECT COUNT(*) FROM player_history") as cur:
                    history = (await cur.fetchone())[0]

                return {
                    "active_tips": tips,
                    "upcoming_fixtures": fixtures,
                    "teams": teams,
                    "player_history_records": history,
                }
        except Exception:
            return {}


    # ── cache API (tabella api_cache) ────────────────────────────────────────

    async def cache_get(self, key: str, now: Optional[datetime] = None) -> Optional[str]:
        """Valore grezzo se presente e non scaduto; una entry scaduta viene eliminata."""
        now = now or datetime.now(timezone.utc)
        async with self.connect() as db:
            async with db.execute(cache_sql.SQL_GET, (key,)) as cur:
                row = await cur.fetchone()
            if row is None:
                return None
            if cache_sql.is_expired(row["expires_at"], now):
                await db.execute(cache_sql.SQL_DELETE, (key,))
                await db.commit()
                return None
            return row["value"]

    async def cache_set(self, key: str, value: str, ttl_type: Optional[str] = None,
                        ttl_seconds: Optional[int] = None, now: Optional[datetime] = None) -> None:
        """Salva un valore; TTL da ttl_seconds oppure dalla mappa dei ttl_type (-1 = permanente)."""
        now = now or datetime.now(timezone.utc)
        ttl = ttl_seconds if ttl_seconds is not None else cache_ttl.ttl_seconds(ttl_type)
        async with self.connect() as db:
            await db.execute(cache_sql.SQL_SET, (key, value, ttl_type,
                                                 cache_sql.compute_expiry(ttl, now), cache_sql.fmt_ts(now)))
            await db.commit()

    async def cache_delete(self, key: str) -> bool:
        async with self.connect() as db:
            cur = await db.execute(cache_sql.SQL_DELETE, (key,))
            await db.commit()
            return cur.rowcount > 0

    async def cache_cleanup_expired(self, now: Optional[datetime] = None) -> int:
        """Elimina le entry scadute; ritorna quante."""
        now = now or datetime.now(timezone.utc)
        async with self.connect() as db:
            cur = await db.execute(cache_sql.SQL_CLEANUP, (cache_sql.fmt_ts(now),))
            await db.commit()
            return cur.rowcount


_db_manager: Optional[DatabaseManager] = None

async def get_db_manager() -> DatabaseManager:
    """Ottieni l'istanza singleton del database manager."""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
        await _db_manager.initialize()
    return _db_manager
