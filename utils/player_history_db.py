"""
Database for storing and retrieving historical player card data.
"""

import sqlite3
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class PlayerHistoricalData:
    """Historical card data for a player."""
    player_name: str
    team_name: str
    league: str
    season: int
    
    # Season statistics
    appearances: int = 0
    minutes_played: int = 0
    yellow_cards: int = 0
    red_cards: int = 0
    fouls_committed: int = 0
    
    # Calculated metrics
    @property
    def yellow_cards_per_game(self) -> float:
        return self.yellow_cards / self.appearances if self.appearances > 0 else 0.0
    
    @property
    def cards_per_90min(self) -> float:
        return (self.yellow_cards * 90) / self.minutes_played if self.minutes_played > 0 else 0.0
    
    @property
    def discipline_score(self) -> float:
        """Overall discipline score (0-10, lower is better)."""
        if self.appearances == 0:
            return 5.0
        
        cards_factor = min(self.yellow_cards_per_game * 5, 8)  # Max 8 for cards
        fouls_factor = min((self.fouls_committed / self.appearances) / 3, 2)  # Max 2 for fouls
        return min(cards_factor + fouls_factor, 10)


class PlayerHistoryDatabase:
    """Manages historical player card data."""
    
    def __init__(self, db_name="player_history.db"):
        self.db_name = db_name
        self._init_db()
        self._populate_sample_data()
    
    def _init_db(self):
        """Initialize database tables."""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        # Player historical data
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS player_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_name TEXT NOT NULL,
                team_name TEXT NOT NULL,
                league TEXT NOT NULL,
                season INTEGER NOT NULL,
                appearances INTEGER DEFAULT 0,
                minutes_played INTEGER DEFAULT 0,
                yellow_cards INTEGER DEFAULT 0,
                red_cards INTEGER DEFAULT 0,
                fouls_committed INTEGER DEFAULT 0,
                position TEXT DEFAULT '',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(player_name, team_name, league, season)
            )
        """)
        
        # Team discipline trends
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS team_discipline (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_name TEXT NOT NULL,
                league TEXT NOT NULL,
                season INTEGER NOT NULL,
                total_yellow_cards INTEGER DEFAULT 0,
                total_red_cards INTEGER DEFAULT 0,
                matches_played INTEGER DEFAULT 0,
                avg_cards_per_match REAL DEFAULT 0.0,
                discipline_rank INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(team_name, league, season)
            )
        """)
        
        # League trends
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS league_trends (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                league TEXT NOT NULL,
                season INTEGER NOT NULL,
                total_matches INTEGER DEFAULT 0,
                total_yellow_cards INTEGER DEFAULT 0,
                total_red_cards INTEGER DEFAULT 0,
                avg_cards_per_match REAL DEFAULT 0.0,
                referee_severity REAL DEFAULT 5.0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(league, season)
            )
        """)
        
        conn.commit()
        conn.close()
    
    def _populate_sample_data(self):
        """Populate with sample historical data for Serie A players."""
        sample_data = [
            # AS Roma players (stagione 2025-26) - SENZA Abraham
            ("Lorenzo Pellegrini", "AS Roma", "Serie A", 2025, 30, 2600, 7, 0, 42, "midfielder"),
            ("Gianluca Mancini", "AS Roma", "Serie A", 2025, 32, 2800, 10, 0, 58, "defender"),
            ("Bryan Cristante", "AS Roma", "Serie A", 2025, 26, 2200, 5, 0, 35, "midfielder"),
            ("Leandro Paredes", "AS Roma", "Serie A", 2025, 23, 2000, 6, 0, 38, "midfielder"),
            ("Evan Ndicka", "AS Roma", "Serie A", 2025, 28, 2400, 4, 0, 30, "defender"),
            ("Angelino", "AS Roma", "Serie A", 2025, 26, 2200, 8, 0, 35, "defender"),
            
            # Inter players (stagione 2025-26)
            ("Nicolò Barella", "Inter", "Serie A", 2025, 32, 2800, 9, 0, 52, "midfielder"),
            ("Alessandro Bastoni", "Inter", "Serie A", 2025, 31, 2700, 7, 0, 33, "defender"),
            ("Hakan Calhanoglu", "Inter", "Serie A", 2025, 30, 2600, 6, 0, 40, "midfielder"),
            ("Denzel Dumfries", "Inter", "Serie A", 2025, 26, 2200, 6, 0, 38, "defender"),
            ("Henrikh Mkhitaryan", "Inter", "Serie A", 2025, 28, 2400, 5, 0, 33, "midfielder"),
            ("Francesco Acerbi", "Inter", "Serie A", 2025, 27, 2300, 7, 0, 42, "defender"),
            
            # AC Milan players (stagione 2025-26) - SENZA Abraham (ceduto al Fenerbahçe)
            ("Theo Hernandez", "AC Milan", "Serie A", 2025, 30, 2600, 10, 1, 43, "defender"),
            ("Fikayo Tomori", "AC Milan", "Serie A", 2025, 27, 2300, 5, 0, 26, "defender"),
            ("Tijjani Reijnders", "AC Milan", "Serie A", 2025, 26, 2200, 4, 0, 30, "midfielder"),
            ("Yunus Musah", "AC Milan", "Serie A", 2025, 23, 1900, 3, 0, 26, "midfielder"),
            ("Matteo Gabbia", "AC Milan", "Serie A", 2025, 22, 1900, 6, 0, 33, "defender"),
            ("Ruben Loftus-Cheek", "AC Milan", "Serie A", 2025, 25, 2100, 4, 0, 28, "midfielder"),
            ("Rafael Leao", "AC Milan", "Serie A", 2025, 24, 2000, 2, 0, 22, "forward"),
            
            # Napoli players (stagione 2025-26)
            ("Stanislav Lobotka", "Napoli", "Serie A", 2025, 31, 2700, 6, 0, 36, "midfielder"),
            ("Giovanni Di Lorenzo", "Napoli", "Serie A", 2025, 33, 2900, 8, 0, 40, "defender"),
            ("Andre-Frank Zambo Anguissa", "Napoli", "Serie A", 2025, 28, 2400, 7, 0, 46, "midfielder"),
            ("Amir Rrahmani", "Napoli", "Serie A", 2025, 30, 2600, 5, 0, 33, "defender"),
            ("Scott McTominay", "Napoli", "Serie A", 2025, 23, 2000, 3, 0, 28, "midfielder"),
            ("Mathias Olivera", "Napoli", "Serie A", 2025, 26, 2200, 5, 0, 30, "defender"),
            
            # Juventus players (stagione 2025-26)
            ("Manuel Locatelli", "Juventus", "Serie A", 2025, 27, 2300, 6, 0, 38, "midfielder"),
            ("Danilo", "Juventus", "Serie A", 2025, 29, 2500, 8, 0, 36, "defender"),
            ("Weston McKennie", "Juventus", "Serie A", 2025, 24, 2100, 4, 0, 30, "midfielder"),
            ("Andrea Cambiaso", "Juventus", "Serie A", 2025, 26, 2200, 5, 0, 33, "defender"),
            ("Pierre Kalulu", "Juventus", "Serie A", 2025, 23, 2000, 3, 0, 26, "defender"),
            ("Khephren Thuram", "Juventus", "Serie A", 2025, 25, 2100, 4, 0, 28, "midfielder"),
            
            # Dati storici 2024 (per confronto)
            ("Lorenzo Pellegrini", "AS Roma", "Serie A", 2024, 32, 2800, 8, 0, 45, "midfielder"),
            ("Nicolò Barella", "Inter", "Serie A", 2024, 34, 3000, 10, 0, 55, "midfielder"),
            ("Theo Hernandez", "AC Milan", "Serie A", 2024, 32, 2850, 11, 1, 45, "defender"),
            ("Giovanni Di Lorenzo", "Napoli", "Serie A", 2024, 35, 3100, 9, 0, 42, "defender"),
            ("Tammy Abraham", "AS Roma", "Serie A", 2024, 30, 2600, 4, 0, 28, "forward"),  # Era alla Roma
            ("Tammy Abraham", "AC Milan", "Serie A", 2024, 18, 1500, 2, 0, 18, "forward"),  # Breve periodo al Milan prima del Fenerbahçe
            
            # Premier League players (stagione 2025-26)
            ("Bruno Fernandes", "Manchester United", "Premier League", 2025, 30, 2600, 8, 0, 42, "midfielder"),
            ("Casemiro", "Manchester United", "Premier League", 2025, 28, 2400, 9, 0, 48, "midfielder"),
            ("Virgil van Dijk", "Liverpool", "Premier League", 2025, 32, 2800, 5, 0, 28, "defender"),
            ("Declan Rice", "Arsenal", "Premier League", 2025, 26, 2200, 6, 0, 35, "midfielder"),
            ("Rodri", "Manchester City", "Premier League", 2025, 29, 2500, 4, 0, 30, "midfielder"),
            ("Conor Gallagher", "Chelsea", "Premier League", 2025, 25, 2100, 7, 0, 38, "midfielder"),
            
            # Bundesliga players (stagione 2025-26)
            ("Joshua Kimmich", "Bayern Munich", "Bundesliga", 2025, 30, 2600, 6, 0, 35, "midfielder"),
            ("Leon Goretzka", "Bayern Munich", "Bundesliga", 2025, 28, 2400, 5, 0, 32, "midfielder"),
            ("Mats Hummels", "Borussia Dortmund", "Bundesliga", 2025, 31, 2700, 8, 0, 40, "defender"),
            ("Granit Xhaka", "Bayer Leverkusen", "Bundesliga", 2025, 29, 2500, 7, 0, 42, "midfielder"),
            
            # La Liga players (stagione 2025-26)
            ("Pedri", "Barcelona", "La Liga", 2025, 27, 2300, 4, 0, 28, "midfielder"),
            ("Gavi", "Barcelona", "La Liga", 2025, 24, 2000, 5, 0, 32, "midfielder"),
            ("Luka Modric", "Real Madrid", "La Liga", 2025, 30, 2600, 3, 0, 25, "midfielder"),
            ("Koke", "Atletico Madrid", "La Liga", 2025, 32, 2800, 8, 0, 45, "midfielder"),
            ("Jose Gimenez", "Atletico Madrid", "La Liga", 2025, 29, 2500, 9, 1, 48, "defender"),
            
            # Ligue 1 players (stagione 2025-26)
            ("Marquinhos", "PSG", "Ligue 1", 2025, 30, 2600, 6, 0, 35, "defender"),
            ("Marco Verratti", "PSG", "Ligue 1", 2025, 31, 2700, 7, 0, 40, "midfielder"),
            ("Seko Fofana", "Lens", "Ligue 1", 2025, 28, 2400, 8, 0, 45, "midfielder"),
            ("Benjamin Andre", "Lille", "Ligue 1", 2025, 27, 2300, 6, 0, 38, "midfielder"),
            
            # Dati storici 2023 (per confronto)
            ("Sandro Tonali", "AC Milan", "Serie A", 2023, 31, 2750, 9, 0, 52, "midfielder"),  # Trasferito al Newcastle
            ("Marcelo Brozovic", "Inter", "Serie A", 2023, 30, 2700, 9, 1, 48, "midfielder"),  # Trasferito Al-Nassr
            ("Adrien Rabiot", "Juventus", "Serie A", 2023, 27, 2300, 6, 0, 35, "midfielder"),  # Trasferito Marsiglia
            ("Federico Chiesa", "Juventus", "Serie A", 2023, 28, 2200, 5, 0, 25, "forward"),  # Trasferito Liverpool
        ]
        
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        for data in sample_data:
            try:
                cursor.execute("""
                    INSERT OR IGNORE INTO player_history 
                    (player_name, team_name, league, season, appearances, minutes_played, 
                     yellow_cards, red_cards, fouls_committed, position)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, data)
            except sqlite3.IntegrityError:
                pass  # Already exists
        
        conn.commit()
        conn.close()
    
    def get_player_history(self, player_name: str, seasons: int = 2) -> List[PlayerHistoricalData]:
        """Get historical data for a player over the last N seasons."""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT player_name, team_name, league, season, appearances, minutes_played,
                   yellow_cards, red_cards, fouls_committed
            FROM player_history
            WHERE LOWER(player_name) LIKE LOWER(?)
            ORDER BY season DESC
            LIMIT ?
        """, (f"%{player_name}%", seasons))
        
        results = cursor.fetchall()
        conn.close()
        
        history = []
        for row in results:
            history.append(PlayerHistoricalData(
                player_name=row[0],
                team_name=row[1],
                league=row[2],
                season=row[3],
                appearances=row[4],
                minutes_played=row[5],
                yellow_cards=row[6],
                red_cards=row[7],
                fouls_committed=row[8]
            ))
        
        return history
    
    def get_team_top_cards(self, team_name: str, season: int, limit: int = 5) -> List[PlayerHistoricalData]:
        """Get the most carded players from a team in a specific season."""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT player_name, team_name, league, season, appearances, minutes_played,
                   yellow_cards, red_cards, fouls_committed
            FROM player_history
            WHERE LOWER(team_name) LIKE LOWER(?) AND season = ?
            ORDER BY yellow_cards DESC, appearances DESC
            LIMIT ?
        """, (f"%{team_name}%", season, limit))
        
        results = cursor.fetchall()
        conn.close()
        
        players = []
        for row in results:
            players.append(PlayerHistoricalData(
                player_name=row[0],
                team_name=row[1],
                league=row[2],
                season=row[3],
                appearances=row[4],
                minutes_played=row[5],
                yellow_cards=row[6],
                red_cards=row[7],
                fouls_committed=row[8]
            ))
        
        return players
    
    def get_league_discipline_trend(self, league: str, season: int) -> Dict[str, float]:
        """Get discipline trends for a league in a season."""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        # Calculate league averages
        cursor.execute("""
            SELECT 
                AVG(yellow_cards * 1.0 / appearances) as avg_yellows_per_game,
                AVG(fouls_committed * 1.0 / appearances) as avg_fouls_per_game,
                COUNT(*) as total_players
            FROM player_history
            WHERE league = ? AND season = ? AND appearances > 10
        """, (league, season))
        
        result = cursor.fetchone()
        conn.close()
        
        if result and result[0] is not None:
            return {
                "avg_yellows_per_game": result[0],
                "avg_fouls_per_game": result[1],
                "total_players": result[2],
                "severity_factor": min(result[0] / 0.25, 2.0)  # Normalize to 0-2 scale
            }
        
        return {
            "avg_yellows_per_game": 0.25,
            "avg_fouls_per_game": 1.5,
            "total_players": 0,
            "severity_factor": 1.0
        }
    
    def find_similar_players(self, player_name: str, position: str, limit: int = 3) -> List[PlayerHistoricalData]:
        """Find players with similar card patterns."""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        # Get the target player's recent stats
        cursor.execute("""
            SELECT yellow_cards, appearances, fouls_committed
            FROM player_history
            WHERE LOWER(player_name) LIKE LOWER(?)
            ORDER BY season DESC
            LIMIT 1
        """, (f"%{player_name}%",))
        
        target = cursor.fetchone()
        if not target:
            return []
        
        target_rate = target[0] / target[1] if target[1] > 0 else 0
        
        # Find similar players
        cursor.execute("""
            SELECT player_name, team_name, league, season, appearances, minutes_played,
                   yellow_cards, red_cards, fouls_committed,
                   ABS((yellow_cards * 1.0 / appearances) - ?) as rate_diff
            FROM player_history
            WHERE position = ? AND season >= 2023 AND appearances > 15
            AND LOWER(player_name) NOT LIKE LOWER(?)
            ORDER BY rate_diff ASC
            LIMIT ?
        """, (target_rate, position, f"%{player_name}%", limit))
        
        results = cursor.fetchall()
        conn.close()
        
        similar = []
        for row in results:
            similar.append(PlayerHistoricalData(
                player_name=row[0],
                team_name=row[1],
                league=row[2],
                season=row[3],
                appearances=row[4],
                minutes_played=row[5],
                yellow_cards=row[6],
                red_cards=row[7],
                fouls_committed=row[8]
            ))
        
        return similar
    
    def get_database_stats(self) -> Dict[str, int]:
        """Get database statistics."""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM player_history")
        total_records = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(DISTINCT player_name) FROM player_history")
        unique_players = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(DISTINCT season) FROM player_history")
        seasons = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            "total_records": total_records,
            "unique_players": unique_players,
            "seasons_covered": seasons
        }
