-- TaskQ Schema Setup for Agents Project
-- This script creates the TaskQ tables and the llm_processing queue
-- Run against the agents database: psql postgresql://postgres:postgres@localhost:5433/agents < scripts/sql/setup_taskq.sql

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- QUEUES TABLE
CREATE TABLE IF NOT EXISTS queues (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT UNIQUE NOT NULL,
    priority_enabled BOOLEAN DEFAULT FALSE,
    concurrency_limit INTEGER DEFAULT 10 CHECK (concurrency_limit > 0),
    delivery_guarantee TEXT NOT NULL CHECK (delivery_guarantee IN ('at_most_once', 'at_least_once', 'exactly_once')),
    retry_strategy JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_queues_name ON queues(name);

-- TASKS TABLE
CREATE TABLE IF NOT EXISTS tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    queue_id UUID NOT NULL REFERENCES queues(id) ON DELETE CASCADE,
    status TEXT NOT NULL CHECK (status IN ('pending', 'claimed', 'running', 'completed', 'failed', 'dead_letter')),
    payload JSONB NOT NULL,
    priority INTEGER,
    scheduled_at TIMESTAMPTZ DEFAULT now(),
    claimed_by TEXT,
    claimed_at TIMESTAMPTZ,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    attempts INTEGER DEFAULT 0 CHECK (attempts >= 0),
    max_attempts INTEGER NOT NULL CHECK (max_attempts > 0),
    last_error JSONB,
    idempotency_key TEXT UNIQUE,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_queue_status ON tasks(queue_id, status);
CREATE INDEX IF NOT EXISTS idx_tasks_scheduled_at ON tasks(scheduled_at) WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS idx_tasks_claimed_by ON tasks(claimed_by) WHERE claimed_by IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_tasks_idempotency_key ON tasks(idempotency_key) WHERE idempotency_key IS NOT NULL;

-- TASK HISTORY TABLE
CREATE TABLE IF NOT EXISTS task_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    attempt INTEGER NOT NULL CHECK (attempt > 0),
    node_id TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ,
    error JSONB,
    result JSONB,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_task_history_task_id ON task_history(task_id);
CREATE INDEX IF NOT EXISTS idx_task_history_node_id ON task_history(node_id);
CREATE INDEX IF NOT EXISTS idx_task_history_created_at ON task_history(created_at);

-- SCHEDULES TABLE
CREATE TABLE IF NOT EXISTS schedules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    queue_id UUID NOT NULL REFERENCES queues(id) ON DELETE CASCADE,
    cron_expression TEXT NOT NULL,
    payload JSONB NOT NULL,
    enabled BOOLEAN DEFAULT TRUE,
    last_run_at TIMESTAMPTZ,
    next_run_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_schedules_enabled_next_run ON schedules(enabled, next_run_at) WHERE enabled = TRUE;

-- CLUSTER NODES TABLE
CREATE TABLE IF NOT EXISTS cluster_nodes (
    id TEXT PRIMARY KEY,
    hostname TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    last_heartbeat TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('active', 'draining', 'dead')),
    capacity INTEGER NOT NULL CHECK (capacity > 0),
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_cluster_nodes_status ON cluster_nodes(status);
CREATE INDEX IF NOT EXISTS idx_cluster_nodes_heartbeat ON cluster_nodes(last_heartbeat);

-- ADMIN ACTIONS TABLE
CREATE TABLE IF NOT EXISTS admin_actions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    action_type TEXT NOT NULL,
    parameters JSONB NOT NULL,
    affected_count INTEGER,
    performed_by TEXT,
    performed_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_admin_actions_type ON admin_actions(action_type);
CREATE INDEX IF NOT EXISTS idx_admin_actions_performed_at ON admin_actions(performed_at);

-- HELPER FUNCTION for updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Drop existing triggers if they exist
DROP TRIGGER IF EXISTS update_queues_updated_at ON queues;
DROP TRIGGER IF EXISTS update_tasks_updated_at ON tasks;
DROP TRIGGER IF EXISTS update_schedules_updated_at ON schedules;

-- Create triggers
CREATE TRIGGER update_queues_updated_at BEFORE UPDATE ON queues
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_tasks_updated_at BEFORE UPDATE ON tasks
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_schedules_updated_at BEFORE UPDATE ON schedules
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Create the llm_processing queue for web API jobs
INSERT INTO queues (name, priority_enabled, concurrency_limit, delivery_guarantee, retry_strategy)
VALUES (
    'llm_processing',
    true,
    10,
    'at_least_once',
    '{"type": "exponential_backoff", "max_attempts": 3, "initial_delay_ms": 5000, "max_delay_ms": 300000, "multiplier": 2.0}'::jsonb
)
ON CONFLICT (name) DO NOTHING;

-- Verify queue was created
SELECT id, name, concurrency_limit, delivery_guarantee FROM queues WHERE name = 'llm_processing';
