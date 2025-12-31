-- Batch Run Tracking Tables
-- Add observability and audit logging for batch processes

-- Table: batch_runs
-- Tracks all batch process executions (weekly updates, predictions, roster refresh)
CREATE TABLE IF NOT EXISTS batch_runs (
    id SERIAL PRIMARY KEY,

    -- Batch identification
    batch_type VARCHAR(50) NOT NULL,  -- 'weekly_update', 'prediction_generation', 'roster_refresh'
    batch_mode VARCHAR(50),            -- 'full', 'odds_only', 'ingest_only', 'schedule_only'
    season_year INT NOT NULL,
    week INT NOT NULL,
    season_type VARCHAR(10),           -- 'reg', 'post'

    -- Execution tracking
    started_at TIMESTAMP NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP,
    duration_seconds INT,
    status VARCHAR(20) NOT NULL,       -- 'running', 'success', 'partial', 'failed'

    -- Batch metrics
    api_calls_made INT DEFAULT 0,
    games_processed INT DEFAULT 0,
    game_logs_added INT DEFAULT 0,
    predictions_generated INT DEFAULT 0,
    predictions_skipped INT DEFAULT 0,  -- Already existed (immutability)
    odds_synced INT DEFAULT 0,
    errors_encountered INT DEFAULT 0,

    -- Diagnostics
    warnings JSONB,                     -- [{step: "box_score", message: "Skipped 3 players"}]
    error_message TEXT,
    extra_data JSONB,                   -- Flexible field for additional context

    -- Audit
    triggered_by VARCHAR(100),          -- 'github_actions', 'manual', 'api'
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for batch_runs
CREATE INDEX IF NOT EXISTS idx_batch_runs_type_week ON batch_runs(batch_type, season_year, week);
CREATE INDEX IF NOT EXISTS idx_batch_runs_status ON batch_runs(status, completed_at DESC);
CREATE INDEX IF NOT EXISTS idx_batch_runs_started ON batch_runs(started_at DESC);

-- Table: data_readiness
-- Materialized view of data availability per week
CREATE TABLE IF NOT EXISTS data_readiness (
    id SERIAL PRIMARY KEY,
    season_year INT NOT NULL,
    week INT NOT NULL,
    season_type VARCHAR(10) NOT NULL DEFAULT 'reg',

    -- Availability flags
    schedule_complete BOOLEAN DEFAULT FALSE,
    game_logs_available BOOLEAN DEFAULT FALSE,
    predictions_available BOOLEAN DEFAULT FALSE,
    draftkings_odds_available BOOLEAN DEFAULT FALSE,
    fanduel_odds_available BOOLEAN DEFAULT FALSE,

    -- Counts
    games_count INT DEFAULT 0,
    game_logs_count INT DEFAULT 0,
    predictions_count INT DEFAULT 0,
    draftkings_odds_count INT DEFAULT 0,
    fanduel_odds_count INT DEFAULT 0,

    -- Freshness
    last_updated TIMESTAMP DEFAULT NOW(),

    UNIQUE(season_year, week, season_type)
);

-- Indexes for data_readiness
CREATE INDEX IF NOT EXISTS idx_data_readiness_week ON data_readiness(season_year, week DESC);
CREATE INDEX IF NOT EXISTS idx_data_readiness_type ON data_readiness(season_type, season_year, week);

-- Comment documentation
COMMENT ON TABLE batch_runs IS 'Audit log for all batch process executions';
COMMENT ON TABLE data_readiness IS 'Data availability status per NFL week';
COMMENT ON COLUMN batch_runs.batch_type IS 'Type of batch process: weekly_update, prediction_generation, roster_refresh';
COMMENT ON COLUMN batch_runs.status IS 'Execution status: running, success, partial, failed';
COMMENT ON COLUMN batch_runs.warnings IS 'JSON array of warnings encountered during execution';
COMMENT ON COLUMN data_readiness.schedule_complete IS 'True if schedule has expected number of games (14-16 for regular season)';
