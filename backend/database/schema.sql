-- LLM Council Database Schema
-- SQLite with WAL mode for better concurrency

-- Conversations table
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    title TEXT DEFAULT 'New Conversation',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    is_pinned INTEGER DEFAULT 0,
    is_hidden INTEGER DEFAULT 0,
    message_count INTEGER DEFAULT 0
);

-- Messages table (both user and assistant messages)
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);

-- Stage 1 responses from council models
CREATE TABLE IF NOT EXISTS stage1_responses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id INTEGER NOT NULL,
    model TEXT NOT NULL,
    response TEXT NOT NULL,
    confidence REAL,
    base_model TEXT,
    sample_id INTEGER,
    created_at TEXT NOT NULL,
    FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE
);

-- Stage 2 peer rankings
CREATE TABLE IF NOT EXISTS stage2_rankings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id INTEGER NOT NULL,
    evaluator_model TEXT NOT NULL,
    raw_ranking TEXT NOT NULL,
    parsed_ranking TEXT,
    debate_round INTEGER DEFAULT 1,
    rubric_scores TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE
);

-- Stage 3 chairman synthesis
CREATE TABLE IF NOT EXISTS stage3_synthesis (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id INTEGER NOT NULL,
    chairman_model TEXT NOT NULL,
    response TEXT NOT NULL,
    meta_evaluation TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE
);

-- Deliberation metadata (label mappings, aggregate rankings, consensus, etc.)
CREATE TABLE IF NOT EXISTS deliberation_metadata (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id INTEGER NOT NULL UNIQUE,
    label_to_model TEXT NOT NULL,
    aggregate_rankings TEXT,
    consensus TEXT,
    voting_method TEXT,
    features TEXT,
    stage1_consensus TEXT,
    debate_history TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_stage1_message ON stage1_responses(message_id);
CREATE INDEX IF NOT EXISTS idx_stage2_message ON stage2_rankings(message_id);
CREATE INDEX IF NOT EXISTS idx_stage3_message ON stage3_synthesis(message_id);
CREATE INDEX IF NOT EXISTS idx_metadata_message ON deliberation_metadata(message_id);
CREATE INDEX IF NOT EXISTS idx_conversations_pinned ON conversations(is_pinned DESC);
CREATE INDEX IF NOT EXISTS idx_conversations_updated ON conversations(updated_at DESC);

-- API Keys table for authentication
CREATE TABLE IF NOT EXISTS api_keys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key_hash TEXT NOT NULL UNIQUE,          -- SHA-256 hash of the key
    key_prefix TEXT NOT NULL,               -- First 12 chars for identification (e.g., "llmc_abc1234")
    name TEXT NOT NULL,                     -- Human-readable name
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    last_used_at TEXT,
    expires_at TEXT,                        -- NULL = never expires
    is_active INTEGER DEFAULT 1,
    rate_limit_override INTEGER,            -- Custom rate limit (NULL = use default)
    permissions TEXT DEFAULT '["read", "write", "stream"]',  -- JSON array of permissions
    metadata TEXT                           -- JSON object for custom data
);

-- API Key usage audit log
CREATE TABLE IF NOT EXISTS api_key_audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    api_key_id INTEGER NOT NULL,
    action TEXT NOT NULL,                   -- 'request', 'rate_limited', 'expired', 'revoked', 'insufficient_permissions'
    endpoint TEXT,
    ip_address TEXT,
    user_agent TEXT,
    request_id TEXT,                        -- UUID for request correlation
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (api_key_id) REFERENCES api_keys(id) ON DELETE CASCADE
);

-- API key indexes
CREATE INDEX IF NOT EXISTS idx_api_keys_hash ON api_keys(key_hash);
CREATE INDEX IF NOT EXISTS idx_api_keys_prefix ON api_keys(key_prefix);
CREATE INDEX IF NOT EXISTS idx_api_keys_active ON api_keys(is_active);
CREATE INDEX IF NOT EXISTS idx_audit_log_key ON api_key_audit_log(api_key_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_created ON api_key_audit_log(created_at);
