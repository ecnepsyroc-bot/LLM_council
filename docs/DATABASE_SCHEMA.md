# Database Schema Documentation

LLM Council uses SQLite with WAL (Write-Ahead Logging) mode for improved concurrency.

## Overview

The database consists of 8 tables organized into two main functional areas:

1. **Conversation Data** - Stores deliberations and their stages
2. **Authentication** - API key management and audit logging

## Entity Relationship Diagram

```
┌─────────────────┐          ┌──────────────┐
│  conversations  │──1:N────▶│   messages   │
└─────────────────┘          └──────┬───────┘
                                    │
                    ┌───────────────┼───────────────┬─────────────────┐
                    │               │               │                 │
                    ▼               ▼               ▼                 ▼
          ┌─────────────────┐ ┌───────────────┐ ┌─────────────────┐ ┌────────────────────┐
          │stage1_responses │ │stage2_rankings│ │stage3_synthesis │ │deliberation_metadata│
          └─────────────────┘ └───────────────┘ └─────────────────┘ └────────────────────┘

┌──────────────┐          ┌─────────────────────┐
│   api_keys   │──1:N────▶│  api_key_audit_log  │
└──────────────┘          └─────────────────────┘
```

## Tables

### conversations

Stores conversation metadata.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | TEXT | PRIMARY KEY | UUID identifier |
| title | TEXT | DEFAULT 'New Conversation' | Auto-generated or user-defined title |
| created_at | TEXT | NOT NULL | ISO 8601 timestamp |
| updated_at | TEXT | NOT NULL | ISO 8601 timestamp, updated on new messages |
| is_pinned | INTEGER | DEFAULT 0 | Boolean flag (0=false, 1=true) |
| is_hidden | INTEGER | DEFAULT 0 | Boolean flag for soft-hiding |
| message_count | INTEGER | DEFAULT 0 | Cached count for performance |

**Indexes:**
- `idx_conversations_pinned` - For sorting pinned conversations first
- `idx_conversations_updated` - For sorting by most recent activity

### messages

Stores both user queries and assistant responses.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | Unique message ID |
| conversation_id | TEXT | NOT NULL, FK | Reference to conversation |
| role | TEXT | NOT NULL, CHECK | Either 'user' or 'assistant' |
| content | TEXT | | User message content (NULL for assistant) |
| created_at | TEXT | NOT NULL | ISO 8601 timestamp |

**Foreign Key:** `conversation_id` → `conversations(id)` ON DELETE CASCADE

**Index:** `idx_messages_conversation` - For efficient conversation retrieval

### stage1_responses

Individual LLM responses from the council models (Stage 1).

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | Unique response ID |
| message_id | INTEGER | NOT NULL, FK | Reference to assistant message |
| model | TEXT | NOT NULL | OpenRouter model identifier |
| response | TEXT | NOT NULL | Full model response text |
| confidence | REAL | | Model's confidence score (0.0-1.0) |
| base_model | TEXT | | For multi-sample, the original model |
| sample_id | INTEGER | | Sample number for multi-sample mode |
| created_at | TEXT | NOT NULL | ISO 8601 timestamp |

**Foreign Key:** `message_id` → `messages(id)` ON DELETE CASCADE

**Index:** `idx_stage1_message` - For retrieving all Stage 1 responses for a message

### stage2_rankings

Peer evaluations and rankings from each model (Stage 2).

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | Unique ranking ID |
| message_id | INTEGER | NOT NULL, FK | Reference to assistant message |
| evaluator_model | TEXT | NOT NULL | Model that performed the evaluation |
| raw_ranking | TEXT | NOT NULL | Full evaluation text |
| parsed_ranking | TEXT | | JSON array of parsed ranking order |
| debate_round | INTEGER | DEFAULT 1 | Round number for multi-round debates |
| rubric_scores | TEXT | | JSON object of rubric dimension scores |
| created_at | TEXT | NOT NULL | ISO 8601 timestamp |

**Foreign Key:** `message_id` → `messages(id)` ON DELETE CASCADE

**Index:** `idx_stage2_message` - For retrieving all Stage 2 rankings for a message

**Note:** Models evaluate anonymized responses (Response A, B, C) to prevent bias.

### stage3_synthesis

Chairman's final synthesized response (Stage 3).

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | Unique synthesis ID |
| message_id | INTEGER | NOT NULL, FK | Reference to assistant message |
| chairman_model | TEXT | NOT NULL | Model that synthesized the response |
| response | TEXT | NOT NULL | Final synthesized response |
| meta_evaluation | TEXT | | Chairman's meta-analysis if enabled |
| created_at | TEXT | NOT NULL | ISO 8601 timestamp |

**Foreign Key:** `message_id` → `messages(id)` ON DELETE CASCADE

**Index:** `idx_stage3_message` - For retrieving Stage 3 synthesis for a message

### deliberation_metadata

Metadata about the deliberation process.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | Unique metadata ID |
| message_id | INTEGER | NOT NULL, UNIQUE, FK | One-to-one with message |
| label_to_model | TEXT | NOT NULL | JSON: anonymous label → model mapping |
| aggregate_rankings | TEXT | | JSON: computed average rankings |
| consensus | TEXT | | JSON: consensus detection results |
| voting_method | TEXT | | Method used: borda, plurality, etc. |
| features | TEXT | | JSON: enabled features for this deliberation |
| stage1_consensus | TEXT | | JSON: early Stage 1 consensus detection |
| debate_history | TEXT | | JSON: multi-round debate progression |
| created_at | TEXT | NOT NULL | ISO 8601 timestamp |

**Foreign Key:** `message_id` → `messages(id)` ON DELETE CASCADE

**Index:** `idx_metadata_message` - For retrieving metadata for a message

### api_keys

API key storage for authentication.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | Unique key ID |
| key_hash | TEXT | NOT NULL, UNIQUE | Bcrypt hash of the API key |
| key_prefix | TEXT | NOT NULL | First 12 chars for identification |
| name | TEXT | NOT NULL | Human-readable name |
| created_at | TEXT | DEFAULT CURRENT_TIMESTAMP | When key was created |
| last_used_at | TEXT | | Last successful authentication |
| expires_at | TEXT | | NULL = never expires |
| is_active | INTEGER | DEFAULT 1 | Boolean: revoked keys have 0 |
| rate_limit_override | INTEGER | | Custom rate limit (NULL = default) |
| permissions | TEXT | DEFAULT '["read","write","stream"]' | JSON array of permissions |
| metadata | TEXT | | JSON object for custom data |

**Indexes:**
- `idx_api_keys_hash` - For hash lookup (legacy)
- `idx_api_keys_prefix` - For prefix-based lookup (bcrypt)
- `idx_api_keys_active` - For listing active keys

**Security Notes:**
- Keys are hashed with bcrypt (work factor 12)
- Only key_prefix is visible in logs/UI
- Full key is shown once at creation, never again

### api_key_audit_log

Audit trail for API key usage and security events.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | Unique log entry ID |
| api_key_id | INTEGER | NOT NULL, FK | Reference to API key |
| action | TEXT | NOT NULL | Event type (see below) |
| endpoint | TEXT | | API endpoint accessed |
| ip_address | TEXT | | Client IP address |
| user_agent | TEXT | | Client user agent |
| request_id | TEXT | | UUID for request correlation |
| created_at | TEXT | DEFAULT CURRENT_TIMESTAMP | When event occurred |

**Foreign Key:** `api_key_id` → `api_keys(id)` ON DELETE CASCADE

**Indexes:**
- `idx_audit_log_key` - For retrieving logs by key
- `idx_audit_log_created` - For time-based queries

**Action Types:**
- `request` - Successful API request
- `rate_limited` - Request blocked by rate limiter
- `expired` - Request with expired key
- `revoked` - Request with revoked key
- `insufficient_permissions` - Request lacking required permission

## JSON Field Schemas

### label_to_model (deliberation_metadata)

Maps anonymous labels to model identifiers:

```json
{
  "Response A": "openai/gpt-4o",
  "Response B": "anthropic/claude-3.5-sonnet",
  "Response C": "google/gemini-pro"
}
```

### aggregate_rankings (deliberation_metadata)

Computed rankings across all peer evaluations:

```json
[
  {"model": "anthropic/claude-3.5-sonnet", "avg_position": 1.5, "votes": 3},
  {"model": "openai/gpt-4o", "avg_position": 2.0, "votes": 3},
  {"model": "google/gemini-pro", "avg_position": 2.5, "votes": 3}
]
```

### parsed_ranking (stage2_rankings)

Extracted ranking from evaluation text:

```json
["Response B", "Response A", "Response C"]
```

### rubric_scores (stage2_rankings)

Scores per evaluation dimension when rubric mode is enabled:

```json
{
  "accuracy": {"Response A": 8, "Response B": 9, "Response C": 7},
  "clarity": {"Response A": 7, "Response B": 8, "Response C": 9},
  "completeness": {"Response A": 8, "Response B": 9, "Response C": 6}
}
```

### permissions (api_keys)

Array of granted permissions:

```json
["read", "write", "stream", "admin"]
```

Available permissions:
- `read` - Access conversation data
- `write` - Create/modify conversations
- `stream` - Use streaming endpoints
- `admin` - Manage API keys

## Migration Notes

### Bcrypt Migration (v1.1)

API keys originally used SHA-256 hashing. The system now supports both:
- **New keys**: Bcrypt with `$2b$` prefix
- **Legacy keys**: SHA-256 (64-char hex string)

The `verify_api_key_auto()` function detects and handles both formats.

## Performance Considerations

1. **WAL Mode**: Enabled for better read concurrency during deliberations
2. **Busy Timeout**: Set to 30 seconds for write contention
3. **Indexes**: Optimized for common access patterns
4. **Cascading Deletes**: Conversation deletion cleans up all related data

## Backup Recommendations

```bash
# Hot backup (while running)
sqlite3 data/llm_council.db ".backup 'backup.db'"

# Full export
sqlite3 data/llm_council.db .dump > backup.sql
```

See [DEPLOYMENT.md](DEPLOYMENT.md) for full backup procedures.
