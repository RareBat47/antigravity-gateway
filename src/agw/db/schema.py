"""Database schema definitions for Antigravity Gateway."""

INIT_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS accounts (
    id TEXT PRIMARY KEY,
    email_safe TEXT NOT NULL,
    display_name TEXT,
    project_id TEXT,
    tier TEXT DEFAULT 'unknown',
    status TEXT DEFAULT 'active',
    enabled INTEGER DEFAULT 1,
    priority INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used_at TIMESTAMP,
    last_success_at TIMESTAMP,
    last_failure_at TIMESTAMP,
    consecutive_failures INTEGER DEFAULT 0,
    total_requests INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS oauth_credentials_metadata (
    account_id TEXT PRIMARY KEY,
    token_type TEXT DEFAULT 'Bearer',
    has_refresh_token INTEGER DEFAULT 1,
    expires_at INTEGER DEFAULT 0,
    last_refreshed_at TIMESTAMP,
    FOREIGN KEY(account_id) REFERENCES accounts(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS quota_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id TEXT NOT NULL,
    model_id TEXT NOT NULL,
    model_family TEXT NOT NULL,
    remaining_fraction REAL,
    reset_time TEXT,
    source TEXT DEFAULT 'cloudcode',
    confidence REAL DEFAULT 1.0,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(account_id) REFERENCES accounts(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS usage_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id TEXT NOT NULL,
    account_id TEXT NOT NULL,
    model_id TEXT NOT NULL,
    prompt_tokens INTEGER DEFAULT 0,
    completion_tokens INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    latency_ms REAL DEFAULT 0,
    status_code INTEGER DEFAULT 200,
    is_streaming INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(account_id) REFERENCES accounts(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS cooldowns (
    account_id TEXT NOT NULL,
    target_family TEXT NOT NULL, -- 'gemini', 'claude', or 'all'
    cooldown_until TIMESTAMP NOT NULL,
    reason TEXT,
    level INTEGER DEFAULT 1,
    PRIMARY KEY(account_id, target_family),
    FOREIGN KEY(account_id) REFERENCES accounts(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS routing_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id TEXT NOT NULL,
    model_id TEXT NOT NULL,
    selected_account_id TEXT NOT NULL,
    candidate_count INTEGER DEFAULT 1,
    selection_score REAL DEFAULT 0.0,
    action TEXT DEFAULT 'routed',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS health_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id TEXT NOT NULL,
    event_type TEXT NOT NULL, -- 'success', 'rate_limit', 'auth_error', 'failure'
    error_message TEXT,
    latency_ms REAL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(account_id) REFERENCES accounts(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_quota_account ON quota_snapshots(account_id, recorded_at);
CREATE INDEX IF NOT EXISTS idx_usage_account ON usage_events(account_id, created_at);
CREATE INDEX IF NOT EXISTS idx_health_account ON health_events(account_id, created_at);
-- Bug #21: Missing indexes on cooldowns – was doing full table scans on every request
CREATE INDEX IF NOT EXISTS idx_cooldown_account_family ON cooldowns(account_id, target_family);
CREATE INDEX IF NOT EXISTS idx_cooldown_until ON cooldowns(cooldown_until);
"""
