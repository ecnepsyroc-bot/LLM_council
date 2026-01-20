# PostgreSQL Migration Guide

Guide for migrating LLM Council from SQLite to PostgreSQL for high-concurrency deployments.

## When to Migrate

**Stay with SQLite if:**

- Single server deployment
- < 100 concurrent users
- Write operations < 10/second
- Simpler operations preferred

**Migrate to PostgreSQL if:**

- Multiple application instances needed
- High write concurrency required
- Need advanced query capabilities (full-text search, JSONB operators)
- Production deployment with HA requirements

## Prerequisites

```bash
# Install PostgreSQL
# Ubuntu/Debian
sudo apt-get install postgresql postgresql-contrib

# macOS
brew install postgresql

# Windows
# Download from https://www.postgresql.org/download/windows/

# Install Python driver
pip install psycopg2-binary
# Or for async support
pip install asyncpg
```

## Database Setup

### 1. Create Database and User

```sql
-- Connect as postgres superuser
sudo -u postgres psql

-- Create database
CREATE DATABASE llm_council;

-- Create user with password
CREATE USER council_user WITH ENCRYPTED PASSWORD 'your_secure_password';

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE llm_council TO council_user;

-- Connect to the database
\c llm_council

-- Grant schema privileges
GRANT ALL ON SCHEMA public TO council_user;
```

### 2. Create Schema

```sql
-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Conversations table
CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    is_pinned BOOLEAN DEFAULT FALSE,
    is_hidden BOOLEAN DEFAULT FALSE,
    message_count INTEGER DEFAULT 0
);

CREATE INDEX idx_conversations_pinned ON conversations(is_pinned DESC, updated_at DESC);
CREATE INDEX idx_conversations_updated ON conversations(updated_at DESC);

-- Messages table
CREATE TABLE messages (
    id SERIAL PRIMARY KEY,
    conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
    role VARCHAR(10) CHECK (role IN ('user', 'assistant')),
    content TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_messages_conversation ON messages(conversation_id);

-- Stage 1 responses
CREATE TABLE stage1_responses (
    id SERIAL PRIMARY KEY,
    message_id INTEGER REFERENCES messages(id) ON DELETE CASCADE,
    model TEXT NOT NULL,
    response TEXT,
    confidence REAL,
    base_model TEXT,
    sample_id TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_stage1_message ON stage1_responses(message_id);

-- Stage 2 rankings
CREATE TABLE stage2_rankings (
    id SERIAL PRIMARY KEY,
    message_id INTEGER REFERENCES messages(id) ON DELETE CASCADE,
    evaluator_model TEXT NOT NULL,
    raw_ranking TEXT,
    parsed_ranking JSONB,
    debate_round INTEGER DEFAULT 1,
    rubric_scores JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_stage2_message ON stage2_rankings(message_id);

-- Stage 3 synthesis
CREATE TABLE stage3_synthesis (
    id SERIAL PRIMARY KEY,
    message_id INTEGER REFERENCES messages(id) ON DELETE CASCADE,
    chairman_model TEXT NOT NULL,
    response TEXT,
    meta_evaluation TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_stage3_message ON stage3_synthesis(message_id);

-- Deliberation metadata
CREATE TABLE deliberation_metadata (
    id SERIAL PRIMARY KEY,
    message_id INTEGER UNIQUE REFERENCES messages(id) ON DELETE CASCADE,
    label_to_model JSONB,
    aggregate_rankings JSONB,
    consensus JSONB,
    voting_method TEXT,
    features JSONB,
    stage1_consensus JSONB,
    debate_history JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_metadata_message ON deliberation_metadata(message_id);

-- API keys
CREATE TABLE api_keys (
    id SERIAL PRIMARY KEY,
    key_hash TEXT UNIQUE NOT NULL,
    key_prefix VARCHAR(12) NOT NULL,
    name TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_used_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    is_active BOOLEAN DEFAULT TRUE,
    rate_limit_override INTEGER,
    permissions JSONB DEFAULT '[]'::jsonb,
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX idx_api_keys_hash ON api_keys(key_hash);
CREATE INDEX idx_api_keys_prefix ON api_keys(key_prefix);
CREATE INDEX idx_api_keys_active ON api_keys(is_active);

-- API key audit log
CREATE TABLE api_key_audit_log (
    id SERIAL PRIMARY KEY,
    api_key_id INTEGER REFERENCES api_keys(id) ON DELETE SET NULL,
    action TEXT NOT NULL,
    endpoint TEXT,
    ip_address TEXT,
    user_agent TEXT,
    request_id TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_audit_key ON api_key_audit_log(api_key_id);
CREATE INDEX idx_audit_created ON api_key_audit_log(created_at);

-- Response cache (new for PostgreSQL)
CREATE TABLE response_cache (
    id SERIAL PRIMARY KEY,
    cache_key TEXT UNIQUE NOT NULL,
    query_hash TEXT NOT NULL,
    stage1_data JSONB,
    stage2_data JSONB,
    stage3_data JSONB,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    hit_count INTEGER DEFAULT 0
);

CREATE INDEX idx_cache_key ON response_cache(cache_key);
CREATE INDEX idx_cache_expires ON response_cache(expires_at);
```

## Code Changes

### 1. Connection Module

Create `backend/database/postgres_connection.py`:

```python
"""PostgreSQL connection management with connection pooling."""

import os
from contextlib import contextmanager
from typing import Generator

import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor

# Connection pool (initialized once)
_connection_pool: pool.ThreadedConnectionPool | None = None


def get_database_url() -> str:
    """Get PostgreSQL connection URL from environment."""
    return os.getenv(
        "DATABASE_URL",
        "postgresql://council_user:password@localhost:5432/llm_council"
    )


def init_pool(min_conn: int = 2, max_conn: int = 10) -> None:
    """Initialize the connection pool."""
    global _connection_pool
    if _connection_pool is None:
        _connection_pool = pool.ThreadedConnectionPool(
            min_conn,
            max_conn,
            get_database_url()
        )


def get_pool() -> pool.ThreadedConnectionPool:
    """Get the connection pool, initializing if needed."""
    if _connection_pool is None:
        init_pool()
    return _connection_pool


@contextmanager
def get_connection() -> Generator[psycopg2.extensions.connection, None, None]:
    """Get a connection from the pool."""
    conn = get_pool().getconn()
    try:
        yield conn
    finally:
        get_pool().putconn(conn)


@contextmanager
def get_cursor(commit: bool = True) -> Generator[RealDictCursor, None, None]:
    """Get a cursor with automatic commit/rollback."""
    with get_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            yield cursor
            if commit:
                conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()


@contextmanager
def transaction() -> Generator[RealDictCursor, None, None]:
    """Execute multiple operations in a transaction."""
    with get_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            yield cursor
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()


def close_pool() -> None:
    """Close all connections in the pool."""
    global _connection_pool
    if _connection_pool is not None:
        _connection_pool.closeall()
        _connection_pool = None
```

### 2. Environment Configuration

Update `.env`:

```bash
# Database selection
DATABASE_TYPE=postgresql  # or 'sqlite'

# PostgreSQL settings
DATABASE_URL=postgresql://council_user:password@localhost:5432/llm_council

# Connection pool settings
DB_POOL_MIN=2
DB_POOL_MAX=10
```

### 3. Repository Updates

Key changes for PostgreSQL compatibility:

```python
# SQLite placeholder
cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))

# PostgreSQL placeholder
cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
```

### 4. Migration Script

Create `backend/database/migrate_to_postgres.py`:

```python
"""Migrate data from SQLite to PostgreSQL."""

import json
import sqlite3
from datetime import datetime

from .postgres_connection import get_cursor, transaction


def migrate_conversations(sqlite_path: str) -> dict:
    """Migrate all data from SQLite to PostgreSQL."""
    stats = {
        "conversations": 0,
        "messages": 0,
        "stage1": 0,
        "stage2": 0,
        "stage3": 0,
        "metadata": 0,
        "api_keys": 0,
        "errors": []
    }

    sqlite_conn = sqlite3.connect(sqlite_path)
    sqlite_conn.row_factory = sqlite3.Row
    sqlite_cur = sqlite_conn.cursor()

    try:
        # Migrate conversations
        sqlite_cur.execute("SELECT * FROM conversations")
        for row in sqlite_cur.fetchall():
            with get_cursor() as pg_cur:
                pg_cur.execute("""
                    INSERT INTO conversations
                    (id, title, created_at, updated_at, is_pinned, is_hidden, message_count)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO NOTHING
                """, (
                    row["id"],
                    row["title"],
                    row["created_at"],
                    row["updated_at"],
                    bool(row["is_pinned"]),
                    bool(row["is_hidden"]),
                    row["message_count"]
                ))
                stats["conversations"] += 1

        # Migrate messages with stage data
        sqlite_cur.execute("SELECT * FROM messages ORDER BY id")
        for msg in sqlite_cur.fetchall():
            with transaction() as pg_cur:
                # Insert message
                pg_cur.execute("""
                    INSERT INTO messages (id, conversation_id, role, content, created_at)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                    RETURNING id
                """, (
                    msg["id"],
                    msg["conversation_id"],
                    msg["role"],
                    msg["content"],
                    msg["created_at"]
                ))
                stats["messages"] += 1

                # Migrate stage1 responses
                sqlite_cur2 = sqlite_conn.cursor()
                sqlite_cur2.execute(
                    "SELECT * FROM stage1_responses WHERE message_id = ?",
                    (msg["id"],)
                )
                for s1 in sqlite_cur2.fetchall():
                    pg_cur.execute("""
                        INSERT INTO stage1_responses
                        (message_id, model, response, confidence, base_model, sample_id)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (
                        s1["message_id"],
                        s1["model"],
                        s1["response"],
                        s1["confidence"],
                        s1["base_model"],
                        s1["sample_id"]
                    ))
                    stats["stage1"] += 1

                # Migrate stage2 rankings
                sqlite_cur2.execute(
                    "SELECT * FROM stage2_rankings WHERE message_id = ?",
                    (msg["id"],)
                )
                for s2 in sqlite_cur2.fetchall():
                    pg_cur.execute("""
                        INSERT INTO stage2_rankings
                        (message_id, evaluator_model, raw_ranking, parsed_ranking,
                         debate_round, rubric_scores)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (
                        s2["message_id"],
                        s2["evaluator_model"],
                        s2["raw_ranking"],
                        s2["parsed_ranking"],  # Already JSON in SQLite
                        s2["debate_round"],
                        s2["rubric_scores"]
                    ))
                    stats["stage2"] += 1

                # Migrate stage3 synthesis
                sqlite_cur2.execute(
                    "SELECT * FROM stage3_synthesis WHERE message_id = ?",
                    (msg["id"],)
                )
                for s3 in sqlite_cur2.fetchall():
                    pg_cur.execute("""
                        INSERT INTO stage3_synthesis
                        (message_id, chairman_model, response, meta_evaluation)
                        VALUES (%s, %s, %s, %s)
                    """, (
                        s3["message_id"],
                        s3["chairman_model"],
                        s3["response"],
                        s3["meta_evaluation"]
                    ))
                    stats["stage3"] += 1

                # Migrate metadata
                sqlite_cur2.execute(
                    "SELECT * FROM deliberation_metadata WHERE message_id = ?",
                    (msg["id"],)
                )
                for meta in sqlite_cur2.fetchall():
                    pg_cur.execute("""
                        INSERT INTO deliberation_metadata
                        (message_id, label_to_model, aggregate_rankings, consensus,
                         voting_method, features, stage1_consensus, debate_history)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        meta["message_id"],
                        meta["label_to_model"],
                        meta["aggregate_rankings"],
                        meta["consensus"],
                        meta["voting_method"],
                        meta["features"],
                        meta["stage1_consensus"],
                        meta["debate_history"]
                    ))
                    stats["metadata"] += 1

        # Migrate API keys
        sqlite_cur.execute("SELECT * FROM api_keys")
        for key in sqlite_cur.fetchall():
            with get_cursor() as pg_cur:
                pg_cur.execute("""
                    INSERT INTO api_keys
                    (key_hash, key_prefix, name, created_at, last_used_at,
                     expires_at, is_active, rate_limit_override, permissions, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (key_hash) DO NOTHING
                """, (
                    key["key_hash"],
                    key["key_prefix"],
                    key["name"],
                    key["created_at"],
                    key["last_used_at"],
                    key["expires_at"],
                    bool(key["is_active"]),
                    key["rate_limit_override"],
                    key["permissions"],
                    key["metadata"]
                ))
                stats["api_keys"] += 1

    except Exception as e:
        stats["errors"].append(str(e))
    finally:
        sqlite_conn.close()

    return stats


def verify_migration(sqlite_path: str) -> dict:
    """Verify migration by comparing record counts."""
    sqlite_conn = sqlite3.connect(sqlite_path)
    sqlite_cur = sqlite_conn.cursor()

    tables = [
        "conversations", "messages", "stage1_responses",
        "stage2_rankings", "stage3_synthesis", "deliberation_metadata", "api_keys"
    ]

    comparison = {}
    for table in tables:
        sqlite_cur.execute(f"SELECT COUNT(*) FROM {table}")
        sqlite_count = sqlite_cur.fetchone()[0]

        with get_cursor() as pg_cur:
            pg_cur.execute(f"SELECT COUNT(*) FROM {table}")
            pg_count = pg_cur.fetchone()["count"]

        comparison[table] = {
            "sqlite": sqlite_count,
            "postgres": pg_count,
            "match": sqlite_count == pg_count
        }

    sqlite_conn.close()
    return comparison


if __name__ == "__main__":
    import sys

    sqlite_path = sys.argv[1] if len(sys.argv) > 1 else "data/council.db"

    print(f"Migrating from {sqlite_path}...")
    stats = migrate_conversations(sqlite_path)
    print(f"Migration complete: {stats}")

    print("\nVerifying...")
    verification = verify_migration(sqlite_path)
    for table, counts in verification.items():
        status = "✓" if counts["match"] else "✗"
        print(f"  {status} {table}: {counts['sqlite']} → {counts['postgres']}")
```

## Migration Steps

### 1. Backup Current Data

```bash
# Backup SQLite database
cp data/council.db data/council.db.backup

# Export to SQL (optional)
sqlite3 data/council.db .dump > data/backup.sql
```

### 2. Set Up PostgreSQL

```bash
# Create database and schema
psql -U postgres -f docs/postgres_schema.sql

# Or use the migration script
python -m backend.database.migrate_to_postgres
```

### 3. Update Configuration

```bash
# Update .env
DATABASE_TYPE=postgresql
DATABASE_URL=postgresql://council_user:password@localhost:5432/llm_council
```

### 4. Run Migration

```bash
# Run migration script
python -m backend.database.migrate_to_postgres data/council.db

# Verify counts
python -c "from backend.database.migrate_to_postgres import verify_migration; print(verify_migration('data/council.db'))"
```

### 5. Test Application

```bash
# Start backend
python -m backend.main

# Run tests
python -m pytest backend/tests/ -v
```

## Rollback Procedure

If migration fails:

```bash
# Restore SQLite configuration
DATABASE_TYPE=sqlite

# Restore backup if needed
cp data/council.db.backup data/council.db

# Restart application
python -m backend.main
```

## Performance Tuning

### PostgreSQL Configuration

Add to `postgresql.conf`:

```ini
# Memory
shared_buffers = 256MB
effective_cache_size = 768MB
work_mem = 16MB

# WAL
wal_buffers = 16MB
checkpoint_completion_target = 0.9

# Connections
max_connections = 100

# Query planning
random_page_cost = 1.1  # For SSD
effective_io_concurrency = 200  # For SSD
```

### Connection Pool Sizing

```python
# Rule of thumb: pool_size = (core_count * 2) + effective_spindle_count
# For 4 cores with SSD: 4 * 2 + 1 = 9 connections

DB_POOL_MIN=2
DB_POOL_MAX=10
```

## Monitoring

### Check Connection Pool Status

```python
from backend.database.postgres_connection import get_pool

pool = get_pool()
print(f"Min: {pool.minconn}, Max: {pool.maxconn}")
print(f"Closed: {pool.closed}")
```

### Query Performance

```sql
-- Slow query log
ALTER SYSTEM SET log_min_duration_statement = 100;  -- Log queries > 100ms

-- Active connections
SELECT * FROM pg_stat_activity WHERE datname = 'llm_council';

-- Table sizes
SELECT relname, pg_size_pretty(pg_total_relation_size(relid))
FROM pg_catalog.pg_statio_user_tables
ORDER BY pg_total_relation_size(relid) DESC;
```
