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
