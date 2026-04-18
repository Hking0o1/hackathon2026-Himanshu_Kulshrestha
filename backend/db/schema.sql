CREATE TABLE IF NOT EXISTS tickets (
    ticket_id        TEXT PRIMARY KEY,
    status           TEXT NOT NULL DEFAULT 'QUEUED',
    tier             INT NOT NULL,
    category         TEXT,
    confidence       FLOAT,
    flags            JSONB DEFAULT '[]',
    resolution_type  TEXT,
    assigned_worker  INT,
    retry_count      INT DEFAULT 0,
    created_at       TIMESTAMPTZ NOT NULL,
    assigned_at      TIMESTAMPTZ,
    resolved_at      TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS audit_log (
    id                 SERIAL PRIMARY KEY,
    ticket_id          TEXT REFERENCES tickets(ticket_id),
    processed_at       TIMESTAMPTZ DEFAULT NOW(),
    worker_id          INT,
    triage_data        JSONB,
    thoughts           JSONB,
    tool_calls         JSONB,
    confidence_final   FLOAT,
    decision           TEXT,
    resolution_type    TEXT,
    flags              JSONB DEFAULT '[]',
    llm_providers      JSONB,
    policy_explanation TEXT,
    total_latency_ms   INT
);

CREATE TABLE IF NOT EXISTS dead_letter_queue (
    id               SERIAL PRIMARY KEY,
    ticket_id        TEXT,
    failure_reason   TEXT,
    last_error       TEXT,
    retry_count      INT,
    ticket_snapshot  JSONB,
    failed_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status);
CREATE INDEX IF NOT EXISTS idx_tickets_tier ON tickets(tier);
CREATE INDEX IF NOT EXISTS idx_audit_ticket ON audit_log(ticket_id);

