-- Batch Step Tracking Migration
-- Adds granular step-level execution tracking for batch processes
-- Idempotent - safe to run multiple times

-- Create batch_execution_steps table
CREATE TABLE IF NOT EXISTS batch_execution_steps (
    id SERIAL PRIMARY KEY,
    batch_run_id INTEGER NOT NULL REFERENCES batch_runs(id) ON DELETE CASCADE,
    step_name VARCHAR(50) NOT NULL,
    step_order INTEGER NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    duration_seconds INTEGER,
    records_processed INTEGER DEFAULT 0,
    error_message TEXT,
    output_log TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_batch_steps_batch_id ON batch_execution_steps(batch_run_id);
CREATE INDEX IF NOT EXISTS idx_batch_steps_status ON batch_execution_steps(status);
CREATE INDEX IF NOT EXISTS idx_batch_steps_step_order ON batch_execution_steps(batch_run_id, step_order);

-- Add comment for documentation
COMMENT ON TABLE batch_execution_steps IS 'Tracks individual steps within batch executions for granular observability';
COMMENT ON COLUMN batch_execution_steps.step_name IS 'Name of the step: schedule, game_logs, odds, predictions';
COMMENT ON COLUMN batch_execution_steps.step_order IS 'Execution order: 1, 2, 3, 4';
COMMENT ON COLUMN batch_execution_steps.status IS 'Step status: pending, running, success, failed, skipped';
COMMENT ON COLUMN batch_execution_steps.output_log IS 'Last 100 lines of step output for debugging';
