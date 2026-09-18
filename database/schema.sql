-- =====================================================
-- FOOTY PREDICTOR - DATABASE SCHEMA
-- Ottimizzato per performance frontend (< 50ms queries) e WAL mode
-- =====================================================

PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA foreign_keys = ON;

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
-- PLAYER HISTORY (Storico disciplinare per modello cartellini)
-- =====================================================
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
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(player_name, team_name, league, season)
);

CREATE INDEX IF NOT EXISTS idx_player_history_name ON player_history(player_name);
CREATE INDEX IF NOT EXISTS idx_player_history_team ON player_history(team_name);
CREATE INDEX IF NOT EXISTS idx_player_history_season ON player_history(season);

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


-- =====================================================
-- CACHE API LOCALE (sostituisce Redis, vedi utils/sqlite_cache.py)
-- Le istruzioni tra i marker sono lette da database/cache_sql.py (SSOT).
-- expires_at NULL = non scade mai; formato 'YYYY-MM-DD HH:MM:SS' UTC.
-- =====================================================
-- BEGIN api_cache
CREATE TABLE IF NOT EXISTS api_cache (key TEXT PRIMARY KEY, value TEXT NOT NULL, ttl_type TEXT, expires_at TIMESTAMP, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE INDEX IF NOT EXISTS idx_api_cache_expires ON api_cache(expires_at);
-- END api_cache

-- =====================================================
-- LEDGER FORWARD (paper trading, gestito da core/ledger.py; letto tra i marker)
-- =====================================================
-- BEGIN ledger
CREATE TABLE IF NOT EXISTS ledger_predictions (fixture_id INTEGER PRIMARY KEY, model TEXT NOT NULL, p1 REAL NOT NULL, px REAL NOT NULL, p2 REAL NOT NULL, p_over_2_5 REAL NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ledger_snapshots (id INTEGER PRIMARY KEY AUTOINCREMENT, fixture_id INTEGER NOT NULL, market TEXT NOT NULL, bookmaker TEXT NOT NULL, bookmaker_id INTEGER, odds_json TEXT NOT NULL, kind TEXT NOT NULL CHECK (kind IN ('pick','close','benchmark_pick','benchmark_close')), captured_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_ledger_snap_fixture ON ledger_snapshots(fixture_id, kind);
CREATE TABLE IF NOT EXISTS ledger_bets (id INTEGER PRIMARY KEY AUTOINCREMENT, strategy TEXT NOT NULL, fixture_id INTEGER NOT NULL, market TEXT NOT NULL, selection TEXT NOT NULL, odds REAL NOT NULL, bookmaker TEXT NOT NULL, p_model REAL, p_used REAL NOT NULL, p_fair REAL NOT NULL, ev REAL NOT NULL, stake_amount REAL NOT NULL, stake_fraction REAL NOT NULL, created_at TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','won','lost','void')), profit REAL, closing_odds REAL, clv REAL, settled_at TEXT, UNIQUE(strategy, fixture_id, market, selection));
CREATE INDEX IF NOT EXISTS idx_ledger_bets_status ON ledger_bets(status, fixture_id);
CREATE TABLE IF NOT EXISTS ledger_bankroll (strategy TEXT PRIMARY KEY, bankroll REAL NOT NULL, high_water_mark REAL NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ledger_player_predictions (fixture_id INTEGER NOT NULL, player_id INTEGER NOT NULL, name TEXT, team TEXT, p_given REAL, start_prob REAL, p_booked REAL NOT NULL, booked INTEGER, created_at TEXT NOT NULL, settled_at TEXT, PRIMARY KEY (fixture_id, player_id));
CREATE TABLE IF NOT EXISTS ledger_results (fixture_id INTEGER PRIMARY KEY, home_goals INTEGER NOT NULL, away_goals INTEGER NOT NULL, settled_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ledger_tips (id INTEGER PRIMARY KEY AUTOINCREMENT, fixture_id INTEGER NOT NULL, key TEXT NOT NULL, family TEXT NOT NULL, probability REAL NOT NULL, fair_odds REAL NOT NULL, min_odds REAL NOT NULL, reliability TEXT NOT NULL, selected INTEGER NOT NULL DEFAULT 0, quote_odds REAL, quote_bookmaker TEXT, created_at TEXT NOT NULL, outcome INTEGER, settled_at TEXT, UNIQUE(fixture_id, key));
CREATE TABLE IF NOT EXISTS ledger_multiples (id INTEGER PRIMARY KEY AUTOINCREMENT, fixture_ids_json TEXT NOT NULL, keys_json TEXT NOT NULL, probability REAL NOT NULL, fair_odds REAL NOT NULL, min_odds REAL NOT NULL, created_at TEXT NOT NULL, outcome INTEGER, settled_at TEXT, UNIQUE(fixture_ids_json, keys_json));
CREATE TABLE IF NOT EXISTS ledger_tip_quotes (id INTEGER PRIMARY KEY AUTOINCREMENT, fixture_id INTEGER NOT NULL, key TEXT NOT NULL, bookmaker TEXT NOT NULL, bookmaker_id INTEGER, odds REAL NOT NULL, captured_at TEXT NOT NULL, kind TEXT NOT NULL CHECK (kind IN ('pick','close')));
CREATE INDEX IF NOT EXISTS idx_ledger_tip_quotes_fx ON ledger_tip_quotes(fixture_id, key, kind);
-- END ledger
