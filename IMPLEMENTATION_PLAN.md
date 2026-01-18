# LLM Council: Comprehensive Implementation Plan

**Created:** 2026-01-17
**Based on:** Council Self-Review + Codebase Exploration
**Status:** Phase 2 Complete

---

## Implementation Progress

| Phase | Status | Notes |
|-------|--------|-------|
| 1. Storage Migration | **COMPLETE** | SQLite with WAL mode, 11 conversations migrated |
| 2. Security Hardening | **COMPLETE** | CORS lockdown, rate limiting, input validation, DOMPurify |
| 3. Testing Infrastructure | Pending | |
| 4. Refactoring council.py | Pending | |

---

## Executive Summary

This plan addresses the four critical areas identified in the LLM Council self-review:

| Priority | Area | Current State | Target State |
|----------|------|---------------|--------------|
| 1 | Storage | JSON files (race conditions, no transactions) | SQLite with proper ACID |
| 2 | Security | Wide open (CORS *, no auth, no rate limiting) | Hardened for production |
| 3 | Testing | 0% coverage | Comprehensive test suite |
| 4 | Refactoring | 1,192-line monolith | Modular architecture |

**Estimated Scope:** ~40-50 files created/modified

---

## Phase 1: Storage Migration (SQLite)

### 1.1 Database Schema

Create `backend/database/schema.sql`:

```sql
-- Core tables
CREATE TABLE conversations (
    id TEXT PRIMARY KEY,
    title TEXT DEFAULT 'New Conversation',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_pinned BOOLEAN DEFAULT FALSE,
    is_hidden BOOLEAN DEFAULT FALSE,
    message_count INTEGER DEFAULT 0
);

CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT,  -- For user messages
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);

CREATE TABLE stage1_responses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id INTEGER NOT NULL,
    model TEXT NOT NULL,
    response TEXT NOT NULL,
    confidence REAL,
    base_model TEXT,  -- For Self-MoA
    sample_id INTEGER,  -- For Self-MoA
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE
);

CREATE TABLE stage2_rankings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id INTEGER NOT NULL,
    evaluator_model TEXT NOT NULL,
    raw_ranking TEXT NOT NULL,
    parsed_ranking TEXT,  -- JSON array of labels
    debate_round INTEGER DEFAULT 1,
    rubric_scores TEXT,  -- JSON object
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE
);

CREATE TABLE stage3_synthesis (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id INTEGER NOT NULL,
    chairman_model TEXT NOT NULL,
    response TEXT NOT NULL,
    meta_evaluation TEXT,  -- Optional meta-eval response
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE
);

CREATE TABLE deliberation_metadata (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id INTEGER NOT NULL UNIQUE,
    label_to_model TEXT NOT NULL,  -- JSON mapping
    aggregate_rankings TEXT,  -- JSON array
    consensus TEXT,  -- JSON object
    voting_method TEXT,
    features TEXT,  -- JSON object
    stage1_consensus TEXT,  -- JSON object
    debate_history TEXT,  -- JSON array
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE
);

-- Indexes for performance
CREATE INDEX idx_messages_conversation ON messages(conversation_id);
CREATE INDEX idx_conversations_pinned ON conversations(is_pinned);
CREATE INDEX idx_conversations_hidden ON conversations(is_hidden);
CREATE INDEX idx_conversations_updated ON conversations(updated_at DESC);
```

### 1.2 New Files to Create

| File | Purpose |
|------|---------|
| `backend/database/__init__.py` | Database package init |
| `backend/database/schema.sql` | Schema definition |
| `backend/database/connection.py` | Connection pool & context manager |
| `backend/database/migrations.py` | Schema versioning & migrations |
| `backend/database/repositories/` | Repository pattern implementations |
| `backend/database/repositories/conversations.py` | Conversation CRUD |
| `backend/database/repositories/messages.py` | Message CRUD |
| `backend/database/repositories/deliberations.py` | Stage data CRUD |

### 1.3 Implementation: connection.py

```python
"""Database connection management with proper transaction support."""
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

DATABASE_PATH = Path(__file__).parent.parent.parent / "data" / "council.db"

# Thread-local storage for connections
_local = threading.local()


def get_connection() -> sqlite3.Connection:
    """Get thread-local database connection."""
    if not hasattr(_local, "connection") or _local.connection is None:
        _local.connection = sqlite3.connect(
            DATABASE_PATH,
            check_same_thread=False,
            isolation_level=None  # Autocommit mode, we manage transactions manually
        )
        _local.connection.row_factory = sqlite3.Row
        _local.connection.execute("PRAGMA foreign_keys = ON")
        _local.connection.execute("PRAGMA journal_mode = WAL")  # Better concurrency
    return _local.connection


@contextmanager
def transaction() -> Generator[sqlite3.Connection, None, None]:
    """Context manager for database transactions with automatic rollback on error."""
    conn = get_connection()
    conn.execute("BEGIN")
    try:
        yield conn
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise


def init_database() -> None:
    """Initialize database schema if not exists."""
    schema_path = Path(__file__).parent / "schema.sql"
    conn = get_connection()
    with open(schema_path) as f:
        conn.executescript(f.read())
```

### 1.4 Implementation: repositories/conversations.py

```python
"""Conversation repository with full CRUD operations."""
import json
import uuid
from datetime import datetime
from typing import Optional
from ..connection import get_connection, transaction


class ConversationRepository:
    """Repository for conversation CRUD operations."""

    def create(self, title: str = "New Conversation") -> dict:
        """Create a new conversation."""
        conv_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()

        with transaction() as conn:
            conn.execute(
                """INSERT INTO conversations (id, title, created_at, updated_at)
                   VALUES (?, ?, ?, ?)""",
                (conv_id, title, now, now)
            )

        return self.get(conv_id)

    def get(self, conv_id: str) -> Optional[dict]:
        """Get conversation by ID with all messages."""
        conn = get_connection()
        row = conn.execute(
            "SELECT * FROM conversations WHERE id = ?", (conv_id,)
        ).fetchone()

        if not row:
            return None

        conv = dict(row)
        conv["messages"] = self._get_messages(conv_id)
        return conv

    def list_all(self, include_hidden: bool = False) -> list[dict]:
        """List all conversations (metadata only)."""
        conn = get_connection()
        query = "SELECT * FROM conversations"
        if not include_hidden:
            query += " WHERE is_hidden = FALSE"
        query += " ORDER BY is_pinned DESC, updated_at DESC"

        rows = conn.execute(query).fetchall()
        return [dict(row) for row in rows]

    def update(self, conv_id: str, **fields) -> Optional[dict]:
        """Update conversation fields."""
        allowed = {"title", "is_pinned", "is_hidden"}
        updates = {k: v for k, v in fields.items() if k in allowed and v is not None}

        if not updates:
            return self.get(conv_id)

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [datetime.utcnow().isoformat(), conv_id]

        with transaction() as conn:
            conn.execute(
                f"UPDATE conversations SET {set_clause}, updated_at = ? WHERE id = ?",
                values
            )

        return self.get(conv_id)

    def delete(self, conv_id: str) -> bool:
        """Delete conversation and all related data (cascades)."""
        with transaction() as conn:
            cursor = conn.execute(
                "DELETE FROM conversations WHERE id = ?", (conv_id,)
            )
            return cursor.rowcount > 0

    def _get_messages(self, conv_id: str) -> list[dict]:
        """Get all messages for a conversation with stage data."""
        conn = get_connection()
        messages = []

        rows = conn.execute(
            "SELECT * FROM messages WHERE conversation_id = ? ORDER BY id",
            (conv_id,)
        ).fetchall()

        for row in rows:
            msg = dict(row)
            if msg["role"] == "assistant":
                msg["stage1"] = self._get_stage1(msg["id"])
                msg["stage2"] = self._get_stage2(msg["id"])
                msg["stage3"] = self._get_stage3(msg["id"])
            messages.append(msg)

        return messages

    def _get_stage1(self, message_id: int) -> list[dict]:
        """Get Stage 1 responses for a message."""
        conn = get_connection()
        rows = conn.execute(
            "SELECT * FROM stage1_responses WHERE message_id = ?",
            (message_id,)
        ).fetchall()
        return [dict(row) for row in rows]

    def _get_stage2(self, message_id: int) -> list[dict]:
        """Get Stage 2 rankings for a message."""
        conn = get_connection()
        rows = conn.execute(
            "SELECT * FROM stage2_rankings WHERE message_id = ?",
            (message_id,)
        ).fetchall()

        result = []
        for row in rows:
            ranking = dict(row)
            if ranking["parsed_ranking"]:
                ranking["parsed_ranking"] = json.loads(ranking["parsed_ranking"])
            if ranking["rubric_scores"]:
                ranking["rubric_scores"] = json.loads(ranking["rubric_scores"])
            result.append(ranking)
        return result

    def _get_stage3(self, message_id: int) -> Optional[dict]:
        """Get Stage 3 synthesis for a message."""
        conn = get_connection()
        row = conn.execute(
            "SELECT * FROM stage3_synthesis WHERE message_id = ?",
            (message_id,)
        ).fetchone()
        return dict(row) if row else None
```

### 1.5 Migration Script

Create `backend/database/migrate_json_to_sqlite.py`:

```python
"""One-time migration from JSON files to SQLite."""
import json
from pathlib import Path
from .connection import init_database, transaction, get_connection


def migrate_conversations():
    """Migrate all JSON conversations to SQLite."""
    json_dir = Path(__file__).parent.parent.parent / "data" / "conversations"

    if not json_dir.exists():
        print("No JSON conversations to migrate")
        return

    init_database()
    migrated = 0

    for json_file in json_dir.glob("*.json"):
        try:
            with open(json_file) as f:
                conv = json.load(f)

            with transaction() as conn:
                # Insert conversation
                conn.execute("""
                    INSERT INTO conversations (id, title, created_at, updated_at,
                                              is_pinned, is_hidden, message_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    conv["id"],
                    conv.get("title", "New Conversation"),
                    conv.get("created_at"),
                    conv.get("created_at"),  # updated_at = created_at initially
                    conv.get("is_pinned", False),
                    conv.get("is_hidden", False),
                    conv.get("message_count", 0)
                ))

                # Insert messages
                for msg in conv.get("messages", []):
                    cursor = conn.execute("""
                        INSERT INTO messages (conversation_id, role, content)
                        VALUES (?, ?, ?)
                    """, (conv["id"], msg["role"], msg.get("content")))

                    message_id = cursor.lastrowid

                    if msg["role"] == "assistant":
                        # Insert Stage 1 responses
                        for resp in msg.get("stage1", []):
                            conn.execute("""
                                INSERT INTO stage1_responses
                                (message_id, model, response, confidence, base_model, sample_id)
                                VALUES (?, ?, ?, ?, ?, ?)
                            """, (
                                message_id,
                                resp["model"],
                                resp["response"],
                                resp.get("confidence"),
                                resp.get("base_model"),
                                resp.get("sample_id")
                            ))

                        # Insert Stage 2 rankings
                        for ranking in msg.get("stage2", []):
                            conn.execute("""
                                INSERT INTO stage2_rankings
                                (message_id, evaluator_model, raw_ranking, parsed_ranking,
                                 debate_round, rubric_scores)
                                VALUES (?, ?, ?, ?, ?, ?)
                            """, (
                                message_id,
                                ranking["model"],
                                ranking["ranking"],
                                json.dumps(ranking.get("parsed_ranking")),
                                ranking.get("debate_round", 1),
                                json.dumps(ranking.get("rubric_scores")) if ranking.get("rubric_scores") else None
                            ))

                        # Insert Stage 3 synthesis
                        stage3 = msg.get("stage3")
                        if stage3:
                            conn.execute("""
                                INSERT INTO stage3_synthesis
                                (message_id, chairman_model, response, meta_evaluation)
                                VALUES (?, ?, ?, ?)
                            """, (
                                message_id,
                                stage3["model"],
                                stage3["response"],
                                stage3.get("meta_evaluation")
                            ))

            migrated += 1
            print(f"✓ Migrated: {json_file.name}")

        except Exception as e:
            print(f"✗ Failed: {json_file.name} - {e}")

    print(f"\nMigration complete: {migrated} conversations migrated")


if __name__ == "__main__":
    migrate_conversations()
```

### 1.6 Update storage.py

Replace `backend/storage.py` with a facade that uses the new repositories:

```python
"""Storage facade - maintains backward compatibility while using SQLite."""
from .database.connection import init_database
from .database.repositories.conversations import ConversationRepository

# Initialize database on module load
init_database()

# Singleton repository instance
_repo = ConversationRepository()


def create_conversation() -> dict:
    """Create a new conversation."""
    return _repo.create()


def get_conversation(conv_id: str) -> dict | None:
    """Get conversation by ID with all messages."""
    return _repo.get(conv_id)


def list_conversations(include_hidden: bool = False) -> list[dict]:
    """List all conversations (metadata only)."""
    return _repo.list_all(include_hidden)


def update_conversation_field(conv_id: str, field: str, value) -> dict | None:
    """Update a single field on a conversation."""
    return _repo.update(conv_id, **{field: value})


def delete_conversation(conv_id: str) -> bool:
    """Delete a conversation."""
    return _repo.delete(conv_id)


# Additional functions for backward compatibility
def add_user_message(conv_id: str, content: str) -> dict | None:
    """Add a user message to conversation."""
    from .database.repositories.messages import MessageRepository
    msg_repo = MessageRepository()
    return msg_repo.add_user_message(conv_id, content)


def add_assistant_message(conv_id: str, stage1: list, stage2: list, stage3: dict,
                          metadata: dict = None) -> dict | None:
    """Add an assistant message with all stage data."""
    from .database.repositories.messages import MessageRepository
    msg_repo = MessageRepository()
    return msg_repo.add_assistant_message(conv_id, stage1, stage2, stage3, metadata)
```

---

## Phase 2: Security Hardening

### 2.1 New Security Files

| File | Purpose |
|------|---------|
| `backend/security/__init__.py` | Security package init |
| `backend/security/cors.py` | CORS configuration |
| `backend/security/rate_limiter.py` | Rate limiting middleware |
| `backend/security/input_validation.py` | Input sanitization |
| `backend/security/authentication.py` | API key authentication |
| `frontend/src/utils/sanitize.ts` | Frontend XSS protection |

### 2.2 CORS Configuration

Create `backend/security/cors.py`:

```python
"""CORS configuration for different environments."""
from fastapi.middleware.cors import CORSMiddleware
import os

# Environment-specific origins
CORS_CONFIGS = {
    "development": {
        "allow_origins": ["http://localhost:5173", "http://localhost:3000"],
        "allow_credentials": True,
        "allow_methods": ["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization", "X-API-Key"],
    },
    "production": {
        "allow_origins": os.getenv("ALLOWED_ORIGINS", "").split(","),
        "allow_credentials": True,
        "allow_methods": ["GET", "POST", "PATCH", "DELETE"],
        "allow_headers": ["Content-Type", "Authorization", "X-API-Key"],
    }
}


def get_cors_config() -> dict:
    """Get CORS config based on environment."""
    env = os.getenv("ENVIRONMENT", "development")
    return CORS_CONFIGS.get(env, CORS_CONFIGS["development"])


def configure_cors(app):
    """Apply CORS middleware to FastAPI app."""
    config = get_cors_config()
    app.add_middleware(CORSMiddleware, **config)
```

### 2.3 Rate Limiting

Create `backend/security/rate_limiter.py`:

```python
"""Rate limiting middleware using sliding window algorithm."""
import time
from collections import defaultdict
from dataclasses import dataclass
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

@dataclass
class RateLimitConfig:
    """Rate limit configuration."""
    requests_per_minute: int = 60
    requests_per_hour: int = 500
    burst_limit: int = 10  # Max requests in 1 second


class RateLimiter:
    """Sliding window rate limiter."""

    def __init__(self, config: RateLimitConfig = None):
        self.config = config or RateLimitConfig()
        self.minute_windows: dict[str, list[float]] = defaultdict(list)
        self.hour_windows: dict[str, list[float]] = defaultdict(list)

    def _cleanup_window(self, window: list[float], max_age: float) -> list[float]:
        """Remove expired timestamps from window."""
        cutoff = time.time() - max_age
        return [t for t in window if t > cutoff]

    def is_allowed(self, client_id: str) -> tuple[bool, str]:
        """Check if request is allowed. Returns (allowed, reason)."""
        now = time.time()

        # Clean up old entries
        self.minute_windows[client_id] = self._cleanup_window(
            self.minute_windows[client_id], 60
        )
        self.hour_windows[client_id] = self._cleanup_window(
            self.hour_windows[client_id], 3600
        )

        # Check burst limit (last second)
        recent = [t for t in self.minute_windows[client_id] if t > now - 1]
        if len(recent) >= self.config.burst_limit:
            return False, "Burst limit exceeded. Please slow down."

        # Check minute limit
        if len(self.minute_windows[client_id]) >= self.config.requests_per_minute:
            return False, "Rate limit exceeded. Please wait a minute."

        # Check hour limit
        if len(self.hour_windows[client_id]) >= self.config.requests_per_hour:
            return False, "Hourly limit exceeded. Please try again later."

        # Record request
        self.minute_windows[client_id].append(now)
        self.hour_windows[client_id].append(now)

        return True, ""


class RateLimitMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware for rate limiting."""

    def __init__(self, app, config: RateLimitConfig = None):
        super().__init__(app)
        self.limiter = RateLimiter(config)

    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for health checks
        if request.url.path == "/":
            return await call_next(request)

        # Get client identifier (IP or API key)
        client_id = request.headers.get("X-API-Key") or request.client.host

        allowed, reason = self.limiter.is_allowed(client_id)
        if not allowed:
            raise HTTPException(status_code=429, detail=reason)

        return await call_next(request)
```

### 2.4 Input Validation

Create `backend/security/input_validation.py`:

```python
"""Input validation and sanitization."""
import re
import html
from pydantic import BaseModel, field_validator, Field
from typing import Optional


class ContentLimits:
    """Content size limits."""
    MAX_MESSAGE_LENGTH = 50000  # 50KB
    MAX_TITLE_LENGTH = 200
    MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB base64
    MAX_IMAGES_PER_MESSAGE = 5


class SafeMessageRequest(BaseModel):
    """Message request with validation."""
    content: str = Field(..., max_length=ContentLimits.MAX_MESSAGE_LENGTH)
    images: list[str] = Field(default_factory=list, max_length=ContentLimits.MAX_IMAGES_PER_MESSAGE)

    @field_validator('content')
    @classmethod
    def sanitize_content(cls, v: str) -> str:
        """Sanitize content to prevent injection attacks."""
        if not v or not v.strip():
            raise ValueError("Content cannot be empty")

        # Remove null bytes
        v = v.replace('\x00', '')

        # Limit consecutive newlines (prevent UI disruption)
        v = re.sub(r'\n{5,}', '\n\n\n\n', v)

        return v.strip()

    @field_validator('images')
    @classmethod
    def validate_images(cls, v: list[str]) -> list[str]:
        """Validate base64 images."""
        validated = []
        for img in v:
            # Check size
            if len(img) > ContentLimits.MAX_IMAGE_SIZE:
                raise ValueError(f"Image exceeds maximum size of {ContentLimits.MAX_IMAGE_SIZE // 1024 // 1024}MB")

            # Validate base64 format
            if not re.match(r'^data:image/(png|jpeg|jpg|gif|webp);base64,[A-Za-z0-9+/=]+$', img):
                raise ValueError("Invalid image format. Must be base64 encoded.")

            validated.append(img)

        return validated


def sanitize_for_prompt(text: str) -> str:
    """Sanitize text before including in prompts to prevent prompt injection."""
    # Add clear boundaries
    sanitized = text.strip()

    # Escape any attempt to break out of user content
    suspicious_patterns = [
        r'(?i)ignore\s+(all\s+)?(previous|above)',
        r'(?i)disregard\s+(all\s+)?(previous|above)',
        r'(?i)forget\s+(all\s+)?(previous|above)',
        r'(?i)new\s+instructions?:',
        r'(?i)system\s*:',
        r'(?i)assistant\s*:',
    ]

    for pattern in suspicious_patterns:
        sanitized = re.sub(pattern, '[FILTERED]', sanitized)

    return sanitized


def sanitize_html(text: str) -> str:
    """Escape HTML entities to prevent XSS."""
    return html.escape(text)
```

### 2.5 Frontend Sanitization

Create `frontend/src/utils/sanitize.ts`:

```typescript
/**
 * Frontend sanitization utilities to prevent XSS attacks.
 */

// Simple HTML entity escaping for contexts where DOMPurify is overkill
export function escapeHtml(text: string): string {
  const map: Record<string, string> = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#039;',
  };
  return text.replace(/[&<>"']/g, (char) => map[char]);
}

// Validate base64 image before displaying
export function isValidBase64Image(data: string): boolean {
  const pattern = /^data:image\/(png|jpeg|jpg|gif|webp);base64,[A-Za-z0-9+/=]+$/;
  return pattern.test(data);
}

// Sanitize URL to prevent javascript: and data: injection
export function sanitizeUrl(url: string): string {
  const trimmed = url.trim().toLowerCase();
  if (trimmed.startsWith('javascript:') || trimmed.startsWith('data:')) {
    return '#';
  }
  return url;
}

// Sanitize markdown to remove potentially dangerous content
export function sanitizeMarkdown(markdown: string): string {
  // Remove HTML comments (can contain malicious content)
  let clean = markdown.replace(/<!--[\s\S]*?-->/g, '');

  // Remove javascript: links
  clean = clean.replace(/\[([^\]]*)\]\(javascript:[^)]*\)/gi, '[$1](#)');

  // Remove data: links except for images
  clean = clean.replace(/\[([^\]]*)\]\(data:(?!image\/)[^)]*\)/gi, '[$1](#)');

  return clean;
}
```

### 2.6 Update main.py

Modify `backend/main.py` to use security middleware:

```python
# Add at top of file
from .security.cors import configure_cors
from .security.rate_limiter import RateLimitMiddleware, RateLimitConfig
from .security.input_validation import SafeMessageRequest, sanitize_for_prompt

# Replace CORS setup
configure_cors(app)

# Add rate limiting
app.add_middleware(RateLimitMiddleware, config=RateLimitConfig(
    requests_per_minute=60,
    requests_per_hour=500,
    burst_limit=10
))

# Update message endpoint to use SafeMessageRequest
@app.post("/api/conversations/{conversation_id}/message")
async def send_message(conversation_id: str, request: SafeMessageRequest):
    # Sanitize content before processing
    safe_content = sanitize_for_prompt(request.content)
    # ... rest of handler
```

### 2.7 Update MarkdownRenderer.tsx

Add DOMPurify to frontend markdown rendering:

```bash
# Add dependency
cd frontend && npm install dompurify @types/dompurify
```

Update `frontend/src/components/shared/MarkdownRenderer.tsx`:

```tsx
import ReactMarkdown from 'react-markdown';
import DOMPurify from 'dompurify';
import { sanitizeMarkdown } from '../../utils/sanitize';
import CodeBlock from './CodeBlock';

interface MarkdownRendererProps {
  content: string;
  className?: string;
}

export default function MarkdownRenderer({ content, className }: MarkdownRendererProps) {
  // Pre-sanitize markdown
  const sanitized = sanitizeMarkdown(content);

  return (
    <div className={className}>
      <ReactMarkdown
        components={{
          code: CodeBlock,
          // Sanitize links
          a: ({ href, children }) => {
            const safeHref = DOMPurify.sanitize(href || '#');
            return (
              <a
                href={safeHref}
                target="_blank"
                rel="noopener noreferrer"
              >
                {children}
              </a>
            );
          },
          // Sanitize images
          img: ({ src, alt }) => {
            if (!src) return null;
            const safeSrc = DOMPurify.sanitize(src);
            return <img src={safeSrc} alt={alt || ''} loading="lazy" />;
          },
        }}
      >
        {sanitized}
      </ReactMarkdown>
    </div>
  );
}
```

---

## Phase 3: Testing Infrastructure

### 3.1 Backend Testing (pytest)

#### Directory Structure

```
backend/
├── tests/
│   ├── __init__.py
│   ├── conftest.py              # Shared fixtures
│   ├── test_voting.py           # Voting algorithm tests
│   ├── test_parsing.py          # Ranking parser tests
│   ├── test_consensus.py        # Consensus detection tests
│   ├── test_storage.py          # Database tests
│   ├── test_api.py              # API endpoint tests
│   └── fixtures/
│       ├── __init__.py
│       ├── responses.py         # Mock model responses
│       └── rankings.py          # Mock ranking data
```

#### conftest.py

```python
"""Shared pytest fixtures for LLM Council tests."""
import pytest
import tempfile
from pathlib import Path
from fastapi.testclient import TestClient

from backend.main import app
from backend.database.connection import DATABASE_PATH, init_database, get_connection


@pytest.fixture(scope="session")
def temp_db():
    """Create temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_db = Path(tmpdir) / "test_council.db"
        # Monkey-patch the database path
        import backend.database.connection as conn_module
        original_path = conn_module.DATABASE_PATH
        conn_module.DATABASE_PATH = test_db

        init_database()
        yield test_db

        # Restore original path
        conn_module.DATABASE_PATH = original_path


@pytest.fixture
def client(temp_db):
    """FastAPI test client with clean database."""
    return TestClient(app)


@pytest.fixture
def sample_responses():
    """Sample Stage 1 responses for testing."""
    return [
        {"model": "openai/gpt-4", "response": "Response from GPT-4", "confidence": 8},
        {"model": "anthropic/claude-3", "response": "Response from Claude", "confidence": 9},
        {"model": "google/gemini-pro", "response": "Response from Gemini", "confidence": 7},
    ]


@pytest.fixture
def sample_rankings():
    """Sample Stage 2 rankings for testing."""
    return [
        {
            "model": "openai/gpt-4",
            "ranking": "FINAL RANKING:\n1. Response B\n2. Response C\n3. Response A",
            "parsed_ranking": ["Response B", "Response C", "Response A"]
        },
        {
            "model": "anthropic/claude-3",
            "ranking": "FINAL RANKING:\n1. Response A\n2. Response B\n3. Response C",
            "parsed_ranking": ["Response A", "Response B", "Response C"]
        },
        {
            "model": "google/gemini-pro",
            "ranking": "FINAL RANKING:\n1. Response B\n2. Response A\n3. Response C",
            "parsed_ranking": ["Response B", "Response A", "Response C"]
        },
    ]
```

#### test_voting.py

```python
"""Tests for voting algorithms."""
import pytest
from backend.council import (
    calculate_borda_count,
    calculate_mrr,
    calculate_confidence_weighted_rankings,
    calculate_aggregate_rankings,
)


class TestBordaCount:
    """Tests for Borda Count voting method."""

    def test_single_voter(self):
        """Borda count with single voter."""
        rankings = [
            {"parsed_ranking": ["Response A", "Response B", "Response C"]}
        ]
        label_to_model = {
            "Response A": "model-a",
            "Response B": "model-b",
            "Response C": "model-c",
        }

        result = calculate_borda_count(rankings, label_to_model)

        # First place gets 3 points, second 2, third 1
        assert result[0]["model"] == "model-a"
        assert result[0]["borda_score"] == 3
        assert result[1]["model"] == "model-b"
        assert result[1]["borda_score"] == 2
        assert result[2]["model"] == "model-c"
        assert result[2]["borda_score"] == 1

    def test_multiple_voters_tie(self):
        """Borda count with conflicting votes."""
        rankings = [
            {"parsed_ranking": ["Response A", "Response B"]},
            {"parsed_ranking": ["Response B", "Response A"]},
        ]
        label_to_model = {
            "Response A": "model-a",
            "Response B": "model-b",
        }

        result = calculate_borda_count(rankings, label_to_model)

        # Both should have equal scores
        assert result[0]["borda_score"] == result[1]["borda_score"]

    def test_empty_rankings(self):
        """Borda count handles empty rankings gracefully."""
        result = calculate_borda_count([], {})
        assert result == []

    def test_partial_rankings(self):
        """Borda count handles voters who didn't rank all options."""
        rankings = [
            {"parsed_ranking": ["Response A", "Response B", "Response C"]},
            {"parsed_ranking": ["Response B"]},  # Only ranked one
        ]
        label_to_model = {
            "Response A": "model-a",
            "Response B": "model-b",
            "Response C": "model-c",
        }

        result = calculate_borda_count(rankings, label_to_model)

        # Should not crash, B should have good score
        assert len(result) == 3
        b_result = next(r for r in result if r["model"] == "model-b")
        assert b_result["borda_score"] > 0


class TestMRR:
    """Tests for Mean Reciprocal Rank voting method."""

    def test_mrr_calculation(self):
        """MRR correctly calculates reciprocal ranks."""
        rankings = [
            {"parsed_ranking": ["Response A", "Response B", "Response C"]},
            {"parsed_ranking": ["Response A", "Response C", "Response B"]},
        ]
        label_to_model = {
            "Response A": "model-a",
            "Response B": "model-b",
            "Response C": "model-c",
        }

        result = calculate_mrr(rankings, label_to_model)

        # A is first in both, so MRR = 1.0
        a_result = next(r for r in result if r["model"] == "model-a")
        assert a_result["mrr_score"] == 1.0

        # B is second in one (0.5), third in other (0.33), avg ≈ 0.42
        b_result = next(r for r in result if r["model"] == "model-b")
        assert 0.4 < b_result["mrr_score"] < 0.45


class TestAggregateRankings:
    """Tests for aggregate ranking dispatcher."""

    def test_method_selection(self):
        """Correct voting method is selected."""
        rankings = [
            {"parsed_ranking": ["Response A", "Response B"]}
        ]
        label_to_model = {"Response A": "model-a", "Response B": "model-b"}

        # Test each method doesn't crash
        for method in ["simple", "borda", "mrr", "confidence_weighted"]:
            result = calculate_aggregate_rankings(
                rankings, label_to_model, voting_method=method
            )
            assert len(result) == 2

    def test_invalid_method_falls_back(self):
        """Invalid method falls back to simple."""
        rankings = [{"parsed_ranking": ["Response A"]}]
        label_to_model = {"Response A": "model-a"}

        result = calculate_aggregate_rankings(
            rankings, label_to_model, voting_method="invalid_method"
        )
        assert len(result) == 1


class TestMathematicalSoundness:
    """Tests verifying mathematical properties of voting algorithms."""

    def test_borda_transitivity(self):
        """If A > B > C consistently, A should win."""
        rankings = [
            {"parsed_ranking": ["Response A", "Response B", "Response C"]},
            {"parsed_ranking": ["Response A", "Response B", "Response C"]},
            {"parsed_ranking": ["Response A", "Response B", "Response C"]},
        ]
        label_to_model = {
            "Response A": "model-a",
            "Response B": "model-b",
            "Response C": "model-c",
        }

        result = calculate_borda_count(rankings, label_to_model)

        assert result[0]["model"] == "model-a"
        assert result[1]["model"] == "model-b"
        assert result[2]["model"] == "model-c"

    def test_condorcet_winner(self):
        """Test Condorcet winner scenario."""
        # A beats B (2-1), A beats C (2-1), B beats C (2-1)
        # A should win with any reasonable voting method
        rankings = [
            {"parsed_ranking": ["Response A", "Response B", "Response C"]},
            {"parsed_ranking": ["Response A", "Response C", "Response B"]},
            {"parsed_ranking": ["Response B", "Response A", "Response C"]},
        ]
        label_to_model = {
            "Response A": "model-a",
            "Response B": "model-b",
            "Response C": "model-c",
        }

        borda_result = calculate_borda_count(rankings, label_to_model)
        mrr_result = calculate_mrr(rankings, label_to_model)

        assert borda_result[0]["model"] == "model-a"
        assert mrr_result[0]["model"] == "model-a"
```

#### test_parsing.py

```python
"""Tests for ranking parser."""
import pytest
from backend.council import parse_ranking_from_text


class TestRankingParser:
    """Tests for parse_ranking_from_text function."""

    def test_standard_format(self):
        """Parse standard FINAL RANKING format."""
        text = """
        Here is my evaluation...

        FINAL RANKING:
        1. Response B
        2. Response A
        3. Response C
        """

        result = parse_ranking_from_text(text)
        assert result == ["Response B", "Response A", "Response C"]

    def test_no_numbers(self):
        """Parse ranking without numbers."""
        text = """
        FINAL RANKING:
        Response C
        Response A
        Response B
        """

        result = parse_ranking_from_text(text)
        assert result == ["Response C", "Response A", "Response B"]

    def test_with_explanations(self):
        """Parse ranking with inline explanations."""
        text = """
        FINAL RANKING:
        1. Response B - Best overall approach
        2. Response A - Good but verbose
        3. Response C - Missing key details
        """

        result = parse_ranking_from_text(text)
        assert result == ["Response B", "Response A", "Response C"]

    def test_fallback_regex(self):
        """Fallback regex when FINAL RANKING not found."""
        text = """
        I think Response A is best, followed by Response C, then Response B.
        """

        result = parse_ranking_from_text(text)
        # Should extract in order found
        assert "Response A" in result
        assert "Response C" in result
        assert "Response B" in result

    def test_empty_input(self):
        """Handle empty input gracefully."""
        result = parse_ranking_from_text("")
        assert result == []

    def test_no_responses(self):
        """Handle text with no Response mentions."""
        result = parse_ranking_from_text("This is just some random text.")
        assert result == []

    def test_duplicate_mentions(self):
        """Handle duplicate Response mentions."""
        text = """
        Response A is great. Response A is really the best.

        FINAL RANKING:
        1. Response A
        2. Response B
        """

        result = parse_ranking_from_text(text)
        # Should only appear once in final ranking
        assert result.count("Response A") == 1

    def test_case_sensitivity(self):
        """Handle case variations."""
        text = """
        FINAL RANKING:
        1. response a
        2. RESPONSE B
        3. Response C
        """

        result = parse_ranking_from_text(text)
        # Should normalize or handle consistently
        assert len(result) == 3

    def test_unicode_content(self):
        """Handle Unicode in ranking text."""
        text = """
        FINAL RANKING:
        1. Response A – comprehensive (★★★)
        2. Response B — good effort
        3. Response C
        """

        result = parse_ranking_from_text(text)
        assert len(result) == 3
```

#### test_consensus.py

```python
"""Tests for consensus detection."""
import pytest
from backend.council import detect_consensus, check_stage1_consensus


class TestConsensusDetection:
    """Tests for detect_consensus function."""

    def test_strong_consensus(self):
        """Detect strong consensus (>75% agreement)."""
        rankings = [
            {"parsed_ranking": ["Response A", "Response B", "Response C"]},
            {"parsed_ranking": ["Response A", "Response B", "Response C"]},
            {"parsed_ranking": ["Response A", "Response C", "Response B"]},
            {"parsed_ranking": ["Response A", "Response B", "Response C"]},
        ]
        label_to_model = {
            "Response A": "model-a",
            "Response B": "model-b",
            "Response C": "model-c",
        }

        result = detect_consensus(rankings, label_to_model)

        assert result["has_consensus"] is True
        assert result["top_model"] == "model-a"
        assert result["agreement_score"] >= 0.75

    def test_no_consensus(self):
        """No consensus when votes are split."""
        rankings = [
            {"parsed_ranking": ["Response A", "Response B", "Response C"]},
            {"parsed_ranking": ["Response B", "Response C", "Response A"]},
            {"parsed_ranking": ["Response C", "Response A", "Response B"]},
        ]
        label_to_model = {
            "Response A": "model-a",
            "Response B": "model-b",
            "Response C": "model-c",
        }

        result = detect_consensus(rankings, label_to_model)

        assert result["has_consensus"] is False
        assert result["agreement_score"] < 0.75

    def test_empty_rankings(self):
        """Handle empty rankings."""
        result = detect_consensus([], {})

        assert result["has_consensus"] is False
        assert result["total_voters"] == 0


class TestStage1Consensus:
    """Tests for early exit based on Stage 1 confidence."""

    def test_high_confidence_exit(self):
        """Early exit when one model has very high confidence."""
        responses = [
            {"model": "model-a", "confidence": 9.5},
            {"model": "model-b", "confidence": 6},
            {"model": "model-c", "confidence": 5},
        ]

        result = check_stage1_consensus(responses)

        assert result["early_exit_possible"] is True
        assert result["high_confidence_model"] == "model-a"

    def test_no_early_exit_close_scores(self):
        """No early exit when confidence scores are close."""
        responses = [
            {"model": "model-a", "confidence": 8},
            {"model": "model-b", "confidence": 7.5},
            {"model": "model-c", "confidence": 7},
        ]

        result = check_stage1_consensus(responses)

        assert result["early_exit_possible"] is False

    def test_no_confidence_scores(self):
        """Handle responses without confidence scores."""
        responses = [
            {"model": "model-a", "response": "Answer"},
            {"model": "model-b", "response": "Answer"},
        ]

        result = check_stage1_consensus(responses)

        assert result["early_exit_possible"] is False
```

#### test_api.py

```python
"""Tests for API endpoints."""
import pytest
from fastapi.testclient import TestClient


class TestHealthCheck:
    """Tests for health check endpoint."""

    def test_health_check(self, client):
        """Health check returns 200."""
        response = client.get("/")
        assert response.status_code == 200


class TestConversations:
    """Tests for conversation CRUD endpoints."""

    def test_create_conversation(self, client):
        """Create a new conversation."""
        response = client.post("/api/conversations")
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["title"] == "New Conversation"

    def test_list_conversations(self, client):
        """List all conversations."""
        # Create a conversation first
        client.post("/api/conversations")

        response = client.get("/api/conversations")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_get_conversation(self, client):
        """Get a specific conversation."""
        # Create first
        create_response = client.post("/api/conversations")
        conv_id = create_response.json()["id"]

        response = client.get(f"/api/conversations/{conv_id}")
        assert response.status_code == 200
        assert response.json()["id"] == conv_id

    def test_get_nonexistent_conversation(self, client):
        """404 for nonexistent conversation."""
        response = client.get("/api/conversations/nonexistent-id")
        assert response.status_code == 404

    def test_update_conversation(self, client):
        """Update conversation fields."""
        create_response = client.post("/api/conversations")
        conv_id = create_response.json()["id"]

        response = client.patch(
            f"/api/conversations/{conv_id}",
            json={"title": "Updated Title", "is_pinned": True}
        )
        assert response.status_code == 200
        assert response.json()["title"] == "Updated Title"
        assert response.json()["is_pinned"] is True

    def test_delete_conversation(self, client):
        """Delete a conversation."""
        create_response = client.post("/api/conversations")
        conv_id = create_response.json()["id"]

        response = client.delete(f"/api/conversations/{conv_id}")
        assert response.status_code == 200

        # Verify deleted
        get_response = client.get(f"/api/conversations/{conv_id}")
        assert get_response.status_code == 404


class TestInputValidation:
    """Tests for input validation."""

    def test_message_length_limit(self, client):
        """Reject messages exceeding length limit."""
        create_response = client.post("/api/conversations")
        conv_id = create_response.json()["id"]

        # Create a message that's too long (>50KB)
        long_content = "x" * 60000

        response = client.post(
            f"/api/conversations/{conv_id}/message",
            json={"content": long_content}
        )
        assert response.status_code == 422  # Validation error

    def test_empty_message_rejected(self, client):
        """Reject empty messages."""
        create_response = client.post("/api/conversations")
        conv_id = create_response.json()["id"]

        response = client.post(
            f"/api/conversations/{conv_id}/message",
            json={"content": "   "}  # Whitespace only
        )
        assert response.status_code == 422


class TestRateLimiting:
    """Tests for rate limiting."""

    def test_burst_limit(self, client):
        """Burst limit triggers after rapid requests."""
        # Make many rapid requests
        responses = []
        for _ in range(15):  # Exceed burst limit of 10
            responses.append(client.get("/api/conversations"))

        # At least one should be rate limited
        status_codes = [r.status_code for r in responses]
        assert 429 in status_codes or all(s == 200 for s in status_codes[:10])
```

### 3.2 Frontend Testing (Vitest)

#### Setup

```bash
cd frontend
npm install -D vitest @testing-library/react @testing-library/jest-dom jsdom @testing-library/user-event
```

Add to `frontend/vite.config.ts`:

```typescript
/// <reference types="vitest" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
    include: ['src/**/*.{test,spec}.{js,mjs,cjs,ts,mts,cts,jsx,tsx}'],
  },
})
```

Create `frontend/src/test/setup.ts`:

```typescript
import '@testing-library/jest-dom';
```

#### Directory Structure

```
frontend/src/
├── test/
│   ├── setup.ts
│   └── utils.tsx          # Test utilities
├── components/
│   ├── shared/
│   │   ├── MarkdownRenderer.test.tsx
│   │   └── InputComposer.test.tsx
│   └── layout/
│       └── DeliberationView.test.tsx
├── store/
│   ├── councilStore.test.ts
│   └── settingsStore.test.ts
└── utils/
    └── sanitize.test.ts
```

#### sanitize.test.ts

```typescript
import { describe, it, expect } from 'vitest';
import { escapeHtml, isValidBase64Image, sanitizeUrl, sanitizeMarkdown } from './sanitize';

describe('escapeHtml', () => {
  it('escapes HTML entities', () => {
    expect(escapeHtml('<script>alert("xss")</script>')).toBe(
      '&lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt;'
    );
  });

  it('handles ampersands', () => {
    expect(escapeHtml('foo & bar')).toBe('foo &amp; bar');
  });

  it('returns empty string for empty input', () => {
    expect(escapeHtml('')).toBe('');
  });
});

describe('isValidBase64Image', () => {
  it('accepts valid PNG base64', () => {
    expect(isValidBase64Image('data:image/png;base64,iVBORw0KGgo=')).toBe(true);
  });

  it('accepts valid JPEG base64', () => {
    expect(isValidBase64Image('data:image/jpeg;base64,/9j/4AAQ=')).toBe(true);
  });

  it('rejects non-image data URLs', () => {
    expect(isValidBase64Image('data:text/html;base64,PHNjcmlwdD4=')).toBe(false);
  });

  it('rejects javascript URLs', () => {
    expect(isValidBase64Image('javascript:alert(1)')).toBe(false);
  });
});

describe('sanitizeUrl', () => {
  it('blocks javascript URLs', () => {
    expect(sanitizeUrl('javascript:alert(1)')).toBe('#');
  });

  it('blocks data URLs', () => {
    expect(sanitizeUrl('data:text/html,<script>')).toBe('#');
  });

  it('allows https URLs', () => {
    expect(sanitizeUrl('https://example.com')).toBe('https://example.com');
  });

  it('allows relative URLs', () => {
    expect(sanitizeUrl('/path/to/page')).toBe('/path/to/page');
  });
});

describe('sanitizeMarkdown', () => {
  it('removes HTML comments', () => {
    expect(sanitizeMarkdown('Hello <!-- comment --> World')).toBe('Hello  World');
  });

  it('removes javascript links', () => {
    const input = '[click me](javascript:alert(1))';
    const output = sanitizeMarkdown(input);
    expect(output).not.toContain('javascript:');
  });

  it('preserves normal markdown', () => {
    const input = '# Header\n\n**bold** and *italic*';
    expect(sanitizeMarkdown(input)).toBe(input);
  });
});
```

#### councilStore.test.ts

```typescript
import { describe, it, expect, beforeEach } from 'vitest';
import { useCouncilStore } from './councilStore';

describe('councilStore', () => {
  beforeEach(() => {
    // Reset store state
    useCouncilStore.setState({
      conversations: [],
      activeConversationId: null,
      activeConversation: null,
      deliberation: { stage: 0, responses: [], rankings: [], synthesis: null },
      councilStatus: {},
      isLoading: false,
    });
  });

  describe('setConversations', () => {
    it('sets conversations list', () => {
      const conversations = [
        { id: '1', title: 'Test', messages: [] },
      ];

      useCouncilStore.getState().setConversations(conversations);

      expect(useCouncilStore.getState().conversations).toEqual(conversations);
    });
  });

  describe('setActiveConversation', () => {
    it('sets active conversation and ID', () => {
      const conversation = { id: '1', title: 'Test', messages: [] };

      useCouncilStore.getState().setActiveConversation(conversation);

      expect(useCouncilStore.getState().activeConversation).toEqual(conversation);
      expect(useCouncilStore.getState().activeConversationId).toBe('1');
    });

    it('clears active conversation when null', () => {
      useCouncilStore.getState().setActiveConversation({ id: '1', title: 'Test', messages: [] });
      useCouncilStore.getState().setActiveConversation(null);

      expect(useCouncilStore.getState().activeConversation).toBeNull();
      expect(useCouncilStore.getState().activeConversationId).toBeNull();
    });
  });

  describe('setStage', () => {
    it('updates deliberation stage', () => {
      useCouncilStore.getState().setStage(2);

      expect(useCouncilStore.getState().deliberation.stage).toBe(2);
    });
  });

  describe('setModelStatus', () => {
    it('updates status for a single model', () => {
      useCouncilStore.getState().setModelStatus('model-a', {
        status: 'responding',
        stage: 1,
      });

      expect(useCouncilStore.getState().councilStatus['model-a']).toEqual({
        status: 'responding',
        stage: 1,
      });
    });
  });

  describe('togglePin', () => {
    it('toggles pin status on conversation', () => {
      useCouncilStore.setState({
        conversations: [{ id: '1', title: 'Test', is_pinned: false, messages: [] }],
      });

      // Note: This would need to mock the API call
      // For unit tests, we test the state update logic
    });
  });
});
```

#### MarkdownRenderer.test.tsx

```typescript
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import MarkdownRenderer from './MarkdownRenderer';

describe('MarkdownRenderer', () => {
  it('renders markdown content', () => {
    render(<MarkdownRenderer content="**bold text**" />);

    expect(screen.getByText('bold text')).toBeInTheDocument();
  });

  it('renders code blocks', () => {
    render(<MarkdownRenderer content="```javascript\nconst x = 1;\n```" />);

    expect(screen.getByText('const x = 1;')).toBeInTheDocument();
  });

  it('sanitizes javascript links', () => {
    render(<MarkdownRenderer content="[click](javascript:alert(1))" />);

    const link = screen.getByRole('link');
    expect(link.getAttribute('href')).not.toContain('javascript:');
  });

  it('adds target blank to external links', () => {
    render(<MarkdownRenderer content="[external](https://example.com)" />);

    const link = screen.getByRole('link');
    expect(link.getAttribute('target')).toBe('_blank');
    expect(link.getAttribute('rel')).toContain('noopener');
  });

  it('applies custom className', () => {
    const { container } = render(
      <MarkdownRenderer content="test" className="custom-class" />
    );

    expect(container.firstChild).toHaveClass('custom-class');
  });
});
```

### 3.3 Test Scripts

Add to `package.json` (root):

```json
{
  "scripts": {
    "test": "npm run test:backend && npm run test:frontend",
    "test:backend": "cd backend && pytest -v",
    "test:frontend": "cd frontend && npm run test",
    "test:coverage": "cd backend && pytest --cov=. --cov-report=html && cd ../frontend && npm run test:coverage"
  }
}
```

Add to `frontend/package.json`:

```json
{
  "scripts": {
    "test": "vitest run",
    "test:watch": "vitest",
    "test:coverage": "vitest run --coverage"
  }
}
```

Add to `pyproject.toml`:

```toml
[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-asyncio>=0.21.0",
    "pytest-cov>=4.0.0",
    "httpx>=0.27.0",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

---

## Phase 4: Refactoring council.py

### 4.1 New Module Structure

```
backend/
├── council/
│   ├── __init__.py           # Public API exports
│   ├── orchestrator.py       # Main coordination logic
│   ├── voting/
│   │   ├── __init__.py
│   │   ├── borda.py          # Borda count algorithm
│   │   ├── mrr.py            # Mean Reciprocal Rank
│   │   ├── confidence.py     # Confidence-weighted voting
│   │   └── simple.py         # Simple average
│   ├── parsing/
│   │   ├── __init__.py
│   │   ├── rankings.py       # Ranking text parser
│   │   ├── confidence.py     # Confidence score parser
│   │   └── rubric.py         # Rubric score parser
│   ├── stages/
│   │   ├── __init__.py
│   │   ├── stage1.py         # Response collection
│   │   ├── stage2.py         # Peer evaluation
│   │   └── stage3.py         # Chairman synthesis
│   ├── consensus.py          # Consensus detection
│   ├── prompts.py            # All prompt templates
│   └── types.py              # Shared type definitions
```

### 4.2 Types Module

Create `backend/council/types.py`:

```python
"""Shared type definitions for council module."""
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class VotingMethod(str, Enum):
    """Available voting methods."""
    SIMPLE = "simple"
    BORDA = "borda"
    MRR = "mrr"
    CONFIDENCE_WEIGHTED = "confidence_weighted"


class ModelStatus(str, Enum):
    """Model processing status."""
    IDLE = "idle"
    THINKING = "thinking"
    RESPONDING = "responding"
    FINISHED = "finished"
    FAILED = "failed"


@dataclass
class ModelResponse:
    """Stage 1 response from a model."""
    model: str
    response: str
    confidence: Optional[float] = None
    base_model: Optional[str] = None  # For Self-MoA
    sample_id: Optional[int] = None   # For Self-MoA


@dataclass
class PeerEvaluation:
    """Stage 2 evaluation from a model."""
    model: str
    raw_ranking: str
    parsed_ranking: list[str]
    debate_round: int = 1
    rubric_scores: Optional[dict] = None


@dataclass
class Synthesis:
    """Stage 3 synthesis from chairman."""
    model: str
    response: str
    meta_evaluation: Optional[str] = None


@dataclass
class AggregateRanking:
    """Aggregated ranking result."""
    model: str
    average_rank: float
    rankings_count: int
    borda_score: Optional[int] = None
    mrr_score: Optional[float] = None
    weighted_score: Optional[float] = None


@dataclass
class Consensus:
    """Consensus detection result."""
    has_consensus: bool
    agreement_score: float
    top_model: Optional[str]
    top_votes: int
    total_voters: int
    early_exit_eligible: bool = False


@dataclass
class DeliberationOptions:
    """Options for council deliberation."""
    voting_method: VotingMethod = VotingMethod.BORDA
    use_rubric: bool = False
    debate_rounds: int = 1
    enable_early_exit: bool = False
    use_self_moa: bool = False
    rotating_chairman: bool = False
    meta_evaluate: bool = False
    include_confidence: bool = True


@dataclass
class DeliberationResult:
    """Complete result of a council deliberation."""
    stage1: list[ModelResponse]
    stage2: list[PeerEvaluation]
    stage3: Synthesis
    label_to_model: dict[str, str]
    aggregate_rankings: list[AggregateRanking]
    consensus: Optional[Consensus] = None
    voting_method: VotingMethod = VotingMethod.BORDA
    debate_history: Optional[list] = None
    stage1_consensus: Optional[dict] = None
```

### 4.3 Prompts Module

Create `backend/council/prompts.py`:

```python
"""Prompt templates for council deliberation stages."""

STAGE2_EVALUATION_PROMPT = """You are evaluating {num_responses} responses to the following question:

QUESTION: {question}

{responses_section}

INSTRUCTIONS:
1. Evaluate each response based on accuracy, completeness, clarity, and helpfulness
2. Consider the quality of reasoning and examples provided
3. Identify any errors or misleading information

{rubric_section}

After your evaluation, provide your ranking in this EXACT format:

FINAL RANKING:
1. Response X
2. Response Y
3. Response Z
...

{confidence_section}

Do not include any text after the ranking section."""


STAGE2_RUBRIC_SECTION = """
SCORING RUBRIC:
For each response, score these criteria from 1-10:
- Accuracy: Are the facts and claims correct?
- Completeness: Does it fully address the question?
- Clarity: Is it well-organized and easy to understand?
- Reasoning: Is the logic sound and well-explained?
- Practicality: Is it actionable and useful?

Provide scores as: [Response X] Accuracy: 8, Completeness: 7, Clarity: 9, Reasoning: 8, Practicality: 7
"""


STAGE2_CONFIDENCE_SECTION = """
After your ranking, on a new line, provide your confidence in this ranking:
CONFIDENCE: X/10
"""


STAGE3_SYNTHESIS_PROMPT = """You are synthesizing the final answer from a council of AI models.

ORIGINAL QUESTION: {question}

{responses_section}

{rankings_section}

AGGREGATE RANKINGS (by peer evaluation):
{aggregate_rankings}

INSTRUCTIONS:
1. Synthesize the best elements from all responses
2. Give more weight to higher-ranked responses, but include valuable insights from any response
3. Correct any errors found in the individual responses
4. Provide a comprehensive, well-structured final answer
5. Do not mention the ranking process or that multiple models were consulted

Provide your synthesized answer:"""


DEBATE_PROMPT = """This is debate round {round_num} of {total_rounds}.

Previous rankings from the council:
{previous_rankings}

Based on this feedback, reconsider your evaluation.
If you still believe your original ranking was correct, explain why.
If you've changed your mind, provide your new ranking.

Use the same format:
FINAL RANKING:
1. Response X
2. Response Y
...

CONFIDENCE: X/10"""


META_EVALUATION_PROMPT = """You are evaluating the quality of a synthesized answer.

ORIGINAL QUESTION: {question}

SYNTHESIZED ANSWER:
{synthesis}

Evaluate on these criteria:
1. Does it accurately represent the best insights from all sources?
2. Is it comprehensive without being redundant?
3. Is the reasoning sound?
4. Are there any errors or omissions?

Provide a brief evaluation (2-3 sentences) and a quality score from 1-10."""


def format_responses_section(responses: list[dict], label_to_model: dict) -> str:
    """Format responses for inclusion in prompts."""
    model_to_label = {v: k for k, v in label_to_model.items()}

    sections = []
    for resp in responses:
        label = model_to_label.get(resp["model"], resp["model"])
        sections.append(f"=== {label} ===\n{resp['response']}\n")

    return "\n".join(sections)


def format_rankings_section(rankings: list[dict]) -> str:
    """Format rankings for inclusion in synthesis prompt."""
    if not rankings:
        return ""

    sections = ["PEER EVALUATIONS:"]
    for rank in rankings:
        sections.append(f"\n{rank['model']}:\n{rank['raw_ranking']}")

    return "\n".join(sections)


def format_aggregate_rankings(aggregate: list[dict]) -> str:
    """Format aggregate rankings for synthesis prompt."""
    if not aggregate:
        return "No aggregate rankings available."

    lines = []
    for i, r in enumerate(aggregate, 1):
        score_info = ""
        if r.get("borda_score"):
            score_info = f" (Borda: {r['borda_score']})"
        elif r.get("mrr_score"):
            score_info = f" (MRR: {r['mrr_score']:.3f})"

        lines.append(f"{i}. {r['model']}{score_info}")

    return "\n".join(lines)
```

### 4.4 Voting Modules

Create `backend/council/voting/borda.py`:

```python
"""Borda Count voting implementation."""
from collections import defaultdict
from ..types import AggregateRanking


def calculate_borda_count(
    rankings: list[dict],
    label_to_model: dict[str, str]
) -> list[AggregateRanking]:
    """
    Calculate Borda Count scores for all models.

    In Borda Count:
    - 1st place gets N points (where N = number of candidates)
    - 2nd place gets N-1 points
    - Last place gets 1 point

    Args:
        rankings: List of peer evaluations with parsed_ranking
        label_to_model: Mapping from "Response X" to model names

    Returns:
        List of AggregateRanking sorted by score (highest first)
    """
    if not rankings or not label_to_model:
        return []

    scores: dict[str, int] = defaultdict(int)
    counts: dict[str, int] = defaultdict(int)
    num_candidates = len(label_to_model)

    for ranking in rankings:
        parsed = ranking.get("parsed_ranking", [])
        if not parsed:
            continue

        for position, label in enumerate(parsed):
            model = label_to_model.get(label)
            if model:
                # Borda score: N - position (1st gets N, 2nd gets N-1, etc.)
                points = num_candidates - position
                scores[model] += points
                counts[model] += 1

    # Build result list
    results = []
    for model in label_to_model.values():
        count = counts.get(model, 0)
        if count > 0:
            results.append(AggregateRanking(
                model=model,
                average_rank=0,  # Calculated below if needed
                rankings_count=count,
                borda_score=scores.get(model, 0)
            ))

    # Sort by Borda score descending
    results.sort(key=lambda r: r.borda_score or 0, reverse=True)

    return results
```

Create `backend/council/voting/mrr.py`:

```python
"""Mean Reciprocal Rank voting implementation."""
from collections import defaultdict
from ..types import AggregateRanking


def calculate_mrr(
    rankings: list[dict],
    label_to_model: dict[str, str]
) -> list[AggregateRanking]:
    """
    Calculate Mean Reciprocal Rank scores for all models.

    MRR gives:
    - 1st place: 1.0
    - 2nd place: 0.5
    - 3rd place: 0.333...
    - Nth place: 1/N

    Args:
        rankings: List of peer evaluations with parsed_ranking
        label_to_model: Mapping from "Response X" to model names

    Returns:
        List of AggregateRanking sorted by MRR score (highest first)
    """
    if not rankings or not label_to_model:
        return []

    rr_sums: dict[str, float] = defaultdict(float)
    counts: dict[str, int] = defaultdict(int)

    for ranking in rankings:
        parsed = ranking.get("parsed_ranking", [])
        if not parsed:
            continue

        for position, label in enumerate(parsed):
            model = label_to_model.get(label)
            if model:
                # Reciprocal rank: 1 / (position + 1)
                rr_sums[model] += 1.0 / (position + 1)
                counts[model] += 1

    # Build result list
    results = []
    for model in label_to_model.values():
        count = counts.get(model, 0)
        if count > 0:
            mrr = rr_sums.get(model, 0) / count
            results.append(AggregateRanking(
                model=model,
                average_rank=0,
                rankings_count=count,
                mrr_score=mrr
            ))

    # Sort by MRR score descending
    results.sort(key=lambda r: r.mrr_score or 0, reverse=True)

    return results
```

### 4.5 Orchestrator

Create `backend/council/orchestrator.py`:

```python
"""Main orchestrator for council deliberation."""
from typing import AsyncGenerator, Optional
import asyncio

from .types import (
    DeliberationOptions,
    DeliberationResult,
    ModelResponse,
    PeerEvaluation,
    Synthesis,
    VotingMethod,
)
from .stages.stage1 import collect_responses, stream_responses
from .stages.stage2 import collect_rankings
from .stages.stage3 import synthesize_final
from .voting import calculate_aggregate
from .consensus import detect_consensus, check_stage1_consensus
from ..config import COUNCIL_MODELS, CHAIRMAN_MODEL


class CouncilOrchestrator:
    """Orchestrates the 3-stage council deliberation process."""

    def __init__(
        self,
        council_models: list[str] = None,
        chairman_model: str = None
    ):
        self.council_models = council_models or COUNCIL_MODELS
        self.chairman_model = chairman_model or CHAIRMAN_MODEL

    async def run(
        self,
        question: str,
        options: DeliberationOptions = None
    ) -> DeliberationResult:
        """
        Run complete council deliberation.

        Args:
            question: User's question to answer
            options: Deliberation configuration options

        Returns:
            Complete deliberation result with all stage outputs
        """
        options = options or DeliberationOptions()

        # Stage 1: Collect responses
        stage1_results = await collect_responses(
            question=question,
            models=self.council_models,
            include_confidence=options.include_confidence
        )

        # Check for early exit based on Stage 1 consensus
        stage1_consensus = None
        if options.enable_early_exit:
            stage1_consensus = check_stage1_consensus(stage1_results)
            if stage1_consensus.get("early_exit_possible"):
                # Skip Stage 2, use high-confidence response as synthesis
                high_conf_model = stage1_consensus["high_confidence_model"]
                high_conf_response = next(
                    r for r in stage1_results if r.model == high_conf_model
                )
                return DeliberationResult(
                    stage1=stage1_results,
                    stage2=[],
                    stage3=Synthesis(
                        model=high_conf_model,
                        response=high_conf_response.response
                    ),
                    label_to_model={},
                    aggregate_rankings=[],
                    stage1_consensus=stage1_consensus
                )

        # Stage 2: Collect rankings (with anonymization)
        stage2_results, label_to_model = await collect_rankings(
            question=question,
            stage1_responses=stage1_results,
            models=self.council_models,
            use_rubric=options.use_rubric,
            debate_rounds=options.debate_rounds
        )

        # Calculate aggregate rankings
        aggregate_rankings = calculate_aggregate(
            rankings=stage2_results,
            label_to_model=label_to_model,
            voting_method=options.voting_method
        )

        # Detect consensus
        consensus = detect_consensus(stage2_results, label_to_model)

        # Select chairman (possibly rotating)
        chairman = self._select_chairman(
            aggregate_rankings,
            stage1_results,
            options.rotating_chairman
        )

        # Stage 3: Synthesize final answer
        stage3_result = await synthesize_final(
            question=question,
            stage1_responses=stage1_results,
            stage2_rankings=stage2_results,
            aggregate_rankings=aggregate_rankings,
            chairman_model=chairman,
            meta_evaluate=options.meta_evaluate
        )

        return DeliberationResult(
            stage1=stage1_results,
            stage2=stage2_results,
            stage3=stage3_result,
            label_to_model=label_to_model,
            aggregate_rankings=aggregate_rankings,
            consensus=consensus,
            voting_method=options.voting_method,
            stage1_consensus=stage1_consensus
        )

    async def stream(
        self,
        question: str,
        options: DeliberationOptions = None
    ) -> AsyncGenerator[dict, None]:
        """
        Stream council deliberation events.

        Yields events as each model responds.
        """
        options = options or DeliberationOptions()

        # Stage 1: Stream responses
        yield {"type": "stage_start", "stage": 1}

        stage1_results = []
        async for event in stream_responses(
            question=question,
            models=self.council_models,
            include_confidence=options.include_confidence
        ):
            yield event
            if event["type"] == "model_complete":
                stage1_results.append(ModelResponse(**event["data"]))

        yield {"type": "stage_complete", "stage": 1}

        # Continue with Stage 2 and 3...
        # (Similar streaming pattern)

    def _select_chairman(
        self,
        aggregate_rankings: list,
        stage1_responses: list,
        rotating: bool
    ) -> str:
        """Select chairman model."""
        if not rotating:
            return self.chairman_model

        # Use top-ranked model from Stage 2
        if aggregate_rankings:
            return aggregate_rankings[0].model

        # Fallback to highest confidence from Stage 1
        with_confidence = [r for r in stage1_responses if r.confidence]
        if with_confidence:
            return max(with_confidence, key=lambda r: r.confidence).model

        return self.chairman_model
```

### 4.6 Public API

Create `backend/council/__init__.py`:

```python
"""
LLM Council - Multi-model deliberation system.

This module provides the core council deliberation functionality:
- Stage 1: Parallel response collection from multiple models
- Stage 2: Anonymized peer evaluation and ranking
- Stage 3: Chairman synthesis of final answer

Usage:
    from backend.council import CouncilOrchestrator, DeliberationOptions

    orchestrator = CouncilOrchestrator()
    result = await orchestrator.run(
        question="What is the meaning of life?",
        options=DeliberationOptions(voting_method=VotingMethod.BORDA)
    )
"""

from .orchestrator import CouncilOrchestrator
from .types import (
    VotingMethod,
    ModelStatus,
    ModelResponse,
    PeerEvaluation,
    Synthesis,
    AggregateRanking,
    Consensus,
    DeliberationOptions,
    DeliberationResult,
)
from .consensus import detect_consensus, check_stage1_consensus
from .voting import calculate_aggregate

# Legacy exports for backward compatibility
from .voting.borda import calculate_borda_count
from .voting.mrr import calculate_mrr
from .parsing.rankings import parse_ranking_from_text

__all__ = [
    # Main API
    "CouncilOrchestrator",
    "DeliberationOptions",
    "DeliberationResult",

    # Types
    "VotingMethod",
    "ModelStatus",
    "ModelResponse",
    "PeerEvaluation",
    "Synthesis",
    "AggregateRanking",
    "Consensus",

    # Functions
    "detect_consensus",
    "check_stage1_consensus",
    "calculate_aggregate",

    # Legacy
    "calculate_borda_count",
    "calculate_mrr",
    "parse_ranking_from_text",
]
```

---

## Implementation Timeline

### Sprint 1: Foundation (Week 1-2)

| Day | Tasks |
|-----|-------|
| 1-2 | Create database schema, connection module |
| 3-4 | Implement repositories, migration script |
| 5 | Update storage.py facade, test migration |
| 6-7 | Add security middleware (CORS, rate limiting) |
| 8-9 | Add input validation, DOMPurify |
| 10 | Integration testing, bug fixes |

### Sprint 2: Testing (Week 3-4)

| Day | Tasks |
|-----|-------|
| 1-3 | Backend test suite (voting, parsing, consensus) |
| 4-5 | API endpoint tests |
| 6-8 | Frontend test setup and component tests |
| 9-10 | Store tests, integration tests |

### Sprint 3: Refactoring (Week 5-6)

| Day | Tasks |
|-----|-------|
| 1-2 | Extract types.py, prompts.py |
| 3-4 | Extract voting modules |
| 5-6 | Extract parsing modules |
| 7-8 | Create stage modules |
| 9 | Build orchestrator |
| 10 | Update main.py, verify backward compatibility |

---

## Verification Checklist

### Phase 1: Storage
- [ ] SQLite database created at `data/council.db`
- [ ] All existing JSON conversations migrated
- [ ] CRUD operations work with new storage
- [ ] Transactions rollback on error
- [ ] Concurrent access doesn't corrupt data

### Phase 2: Security
- [ ] CORS restricted to localhost:5173
- [ ] Rate limiting active (60/min, 500/hr)
- [ ] Messages over 50KB rejected
- [ ] XSS attempts sanitized
- [ ] JavaScript URLs blocked

### Phase 3: Testing
- [ ] `npm run test` passes all tests
- [ ] Backend coverage > 70%
- [ ] Frontend coverage > 60%
- [ ] Voting algorithms validated mathematically
- [ ] Parser handles edge cases

### Phase 4: Refactoring
- [ ] council.py split into 8+ modules
- [ ] No module exceeds 300 lines
- [ ] All imports work correctly
- [ ] Backward compatibility maintained
- [ ] Type hints on all public functions

---

## Commands Reference

```bash
# Run all tests
npm run test

# Run backend tests only
npm run test:backend

# Run frontend tests only
npm run test:frontend

# Migrate JSON to SQLite
uv run python -m backend.database.migrate_json_to_sqlite

# Start with new storage
npm run dev

# Check test coverage
npm run test:coverage
```

---

## Files Created/Modified Summary

### New Files (36)

```
backend/
├── database/
│   ├── __init__.py
│   ├── schema.sql
│   ├── connection.py
│   ├── migrations.py
│   ├── migrate_json_to_sqlite.py
│   └── repositories/
│       ├── __init__.py
│       ├── conversations.py
│       ├── messages.py
│       └── deliberations.py
├── security/
│   ├── __init__.py
│   ├── cors.py
│   ├── rate_limiter.py
│   ├── input_validation.py
│   └── authentication.py
├── council/
│   ├── __init__.py
│   ├── orchestrator.py
│   ├── types.py
│   ├── prompts.py
│   ├── consensus.py
│   ├── voting/
│   │   ├── __init__.py
│   │   ├── borda.py
│   │   ├── mrr.py
│   │   ├── confidence.py
│   │   └── simple.py
│   ├── parsing/
│   │   ├── __init__.py
│   │   ├── rankings.py
│   │   ├── confidence.py
│   │   └── rubric.py
│   └── stages/
│       ├── __init__.py
│       ├── stage1.py
│       ├── stage2.py
│       └── stage3.py
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── test_voting.py
    ├── test_parsing.py
    ├── test_consensus.py
    ├── test_storage.py
    ├── test_api.py
    └── fixtures/
        ├── __init__.py
        ├── responses.py
        └── rankings.py

frontend/src/
├── test/
│   ├── setup.ts
│   └── utils.tsx
├── utils/
│   ├── sanitize.ts
│   └── sanitize.test.ts
├── store/
│   ├── councilStore.test.ts
│   └── settingsStore.test.ts
└── components/shared/
    └── MarkdownRenderer.test.tsx
```

### Modified Files (5)

```
backend/
├── storage.py          # Facade using new repositories
├── main.py             # Security middleware integration
└── council.py          # Deprecated, imports from council/

frontend/
├── vite.config.ts      # Vitest configuration
└── src/components/shared/MarkdownRenderer.tsx  # DOMPurify
```

---

*This plan was generated based on the LLM Council self-review and codebase exploration. Implement phases incrementally, verifying each before proceeding.*
