-- =====================================================
-- FOOTY PREDICTOR - DATABASE SCHEMA
-- Ottimizzato per performance frontend (< 50ms queries)
-- =====================================================

-- =====================================================
-- LEAGUES
-- =====================================================
CREATE TABLE IF NOT EXISTS leagues (
    id INTEGER PRIMARY KEY,
    key VARCHAR(50) UNIQUE NOT NULL,  -- 'serie_a', 'premier_league', etc.
    name VARCHAR(100) NOT NULL,
    country VARCHAR(50) NOT NULL,
    country_code VARCHAR(5) NOT NULL,
    flag VARCHAR(10) NOT NULL,
    api_league_id INTEGER NOT NULL,
    enabled BOOLEAN DEFAULT TRUE,
    priority INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_leagues_enabled ON leagues(enabled);
CREATE INDEX idx_leagues_priority ON leagues(priority);

-- =====================================================
-- TEAMS
-- =====================================================
CREATE TABLE IF NOT EXISTS teams (
    id INTEGER PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    short_name VARCHAR(50),
    logo_url TEXT,
    league_id INTEGER NOT NULL,
    season INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (league_id) REFERENCES leagues(id),
    UNIQUE(id, league_id, season)
);

CREATE INDEX idx_teams_league ON teams(league_id);
CREATE INDEX idx_teams_season ON teams(season);

-- =====================================================
-- FIXTURES (Partite)
-- =====================================================
CREATE TABLE IF NOT EXISTS fixtures (
    id INTEGER PRIMARY KEY,
    league_id INTEGER NOT NULL,
    season INTEGER NOT NULL,
    matchday INTEGER,
    home_team_id INTEGER NOT NULL,
    away_team_id INTEGER NOT NULL,
    match_date TIMESTAMP NOT NULL,
    status VARCHAR(20) DEFAULT 'NS',  -- NS, LIVE, FT, PST, etc.
    home_score INTEGER,
    away_score INTEGER,
    venue VARCHAR(200),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (league_id) REFERENCES leagues(id),
    FOREIGN KEY (home_team_id) REFERENCES teams(id),
    FOREIGN KEY (away_team_id) REFERENCES teams(id)
);

CREATE INDEX idx_fixtures_league ON fixtures(league_id);
CREATE INDEX idx_fixtures_date ON fixtures(match_date);
CREATE INDEX idx_fixtures_status ON fixtures(status);
CREATE INDEX idx_fixtures_home_team ON fixtures(home_team_id);
CREATE INDEX idx_fixtures_away_team ON fixtures(away_team_id);

-- =====================================================
-- BETTING TIPS (Pre-calcolati)
-- =====================================================
CREATE TABLE IF NOT EXISTS betting_tips (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fixture_id INTEGER NOT NULL,
    market VARCHAR(50) NOT NULL,  -- 'BTTS', 'Over_2.5', 'Match_Result', etc.
    selection VARCHAR(50) NOT NULL,  -- 'Yes', 'Over', 'Home', etc.
    confidence FLOAT NOT NULL,  -- 0.0 - 1.0
    percentage FLOAT NOT NULL,  -- 0.0 - 100.0
    odds_min FLOAT,
    odds_max FLOAT,
    reasoning TEXT,
    status VARCHAR(20) DEFAULT 'active',  -- active, expired, won, lost
    calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (fixture_id) REFERENCES fixtures(id),
    UNIQUE(fixture_id, market, selection)
);

CREATE INDEX idx_tips_fixture ON betting_tips(fixture_id);
CREATE INDEX idx_tips_confidence ON betting_tips(confidence DESC);
CREATE INDEX idx_tips_status ON betting_tips(status);
CREATE INDEX idx_tips_market ON betting_tips(market);
CREATE INDEX idx_tips_calculated ON betting_tips(calculated_at);

-- =====================================================
-- PLAYER CARD TIPS (Pre-calcolati)
-- =====================================================
CREATE TABLE IF NOT EXISTS player_card_tips (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fixture_id INTEGER NOT NULL,
    player_id INTEGER NOT NULL,
    player_name VARCHAR(100) NOT NULL,
    team_id INTEGER NOT NULL,
    card_type VARCHAR(20) DEFAULT 'yellow',  -- yellow, red
    confidence FLOAT NOT NULL,
    percentage FLOAT NOT NULL,
    odds_min FLOAT,
    odds_max FLOAT,
    reasoning TEXT,
    status VARCHAR(20) DEFAULT 'active',
    calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (fixture_id) REFERENCES fixtures(id),
    FOREIGN KEY (team_id) REFERENCES teams(id)
);

CREATE INDEX idx_player_tips_fixture ON player_card_tips(fixture_id);
CREATE INDEX idx_player_tips_confidence ON player_card_tips(confidence DESC);
CREATE INDEX idx_player_tips_status ON player_card_tips(status);

-- =====================================================
-- TEAM STATISTICS (Cached)
-- =====================================================
CREATE TABLE IF NOT EXISTS team_statistics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id INTEGER NOT NULL,
    league_id INTEGER NOT NULL,
    season INTEGER NOT NULL,
    matches_played INTEGER DEFAULT 0,
    wins INTEGER DEFAULT 0,
    draws INTEGER DEFAULT 0,
    losses INTEGER DEFAULT 0,
    goals_for INTEGER DEFAULT 0,
    goals_against INTEGER DEFAULT 0,
    clean_sheets INTEGER DEFAULT 0,
    btts_count INTEGER DEFAULT 0,
    over_25_count INTEGER DEFAULT 0,
    cards_yellow INTEGER DEFAULT 0,
    cards_red INTEGER DEFAULT 0,
    form_last_5 VARCHAR(10),  -- 'WWDLL', etc.
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (team_id) REFERENCES teams(id),
    FOREIGN KEY (league_id) REFERENCES leagues(id),
    UNIQUE(team_id, league_id, season)
);

CREATE INDEX idx_team_stats_team ON team_statistics(team_id);
CREATE INDEX idx_team_stats_updated ON team_statistics(updated_at);

-- =====================================================
-- DAILY PICKS (Vista Pre-calcolata per Frontend)
-- =====================================================
CREATE VIEW IF NOT EXISTS daily_picks AS
SELECT 
    bt.id as tip_id,
    bt.fixture_id,
    f.match_date,
    l.name as league_name,
    l.flag as league_flag,
    ht.name as home_team,
    at.name as away_team,
    bt.market,
    bt.selection,
    bt.confidence,
    bt.percentage,
    bt.odds_min,
    bt.odds_max,
    bt.reasoning,
    bt.status
FROM betting_tips bt
JOIN fixtures f ON bt.fixture_id = f.id
JOIN leagues l ON f.league_id = l.id
JOIN teams ht ON f.home_team_id = ht.id
JOIN teams at ON f.away_team_id = at.id
WHERE f.status = 'NS'  -- Solo partite non iniziate
  AND bt.status = 'active'
  AND f.match_date > CURRENT_TIMESTAMP
ORDER BY f.match_date ASC, bt.confidence DESC;

-- =====================================================
-- TOP PLAYER CARDS (Vista Pre-calcolata)
-- =====================================================
CREATE VIEW IF NOT EXISTS top_player_cards AS
SELECT 
    pc.id as tip_id,
    pc.fixture_id,
    f.match_date,
    l.name as league_name,
    l.flag as league_flag,
    ht.name as home_team,
    at.name as away_team,
    pc.player_name,
    t.name as player_team,
    pc.card_type,
    pc.confidence,
    pc.percentage,
    pc.reasoning
FROM player_card_tips pc
JOIN fixtures f ON pc.fixture_id = f.id
JOIN leagues l ON f.league_id = l.id
JOIN teams ht ON f.home_team_id = ht.id
JOIN teams at ON f.away_team_id = at.id
JOIN teams t ON pc.team_id = t.id
WHERE f.status = 'NS'
  AND pc.status = 'active'
  AND f.match_date > CURRENT_TIMESTAMP
ORDER BY f.match_date ASC, pc.confidence DESC
LIMIT 20;

-- =====================================================
-- SYSTEM METADATA
-- =====================================================
CREATE TABLE IF NOT EXISTS system_metadata (
    key VARCHAR(100) PRIMARY KEY,
    value TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Traccia ultimo aggiornamento dati
INSERT OR REPLACE INTO system_metadata (key, value) 
VALUES ('last_data_update', datetime('now'));

-- =====================================================
-- TRIGGERS per aggiornare updated_at
-- =====================================================
CREATE TRIGGER IF NOT EXISTS update_leagues_timestamp 
AFTER UPDATE ON leagues
BEGIN
    UPDATE leagues SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS update_teams_timestamp 
AFTER UPDATE ON teams
BEGIN
    UPDATE teams SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS update_fixtures_timestamp 
AFTER UPDATE ON fixtures
BEGIN
    UPDATE fixtures SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS update_team_stats_timestamp 
AFTER UPDATE ON team_statistics
BEGIN
    UPDATE team_statistics SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

-- =====================================================
-- PERFORMANCE NOTES
-- =====================================================
-- 1. Tutte le query principali hanno indici
-- 2. Le view sono pre-calcolate per query < 50ms
-- 3. I tips sono pre-calcolati, non calcolati on-demand
-- 4. Gli indici su confidence DESC permettono TOP N queries veloci
-- 5. Status field permette di disabilitare tips senza eliminarli

