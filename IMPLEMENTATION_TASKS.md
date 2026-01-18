# LLM Council v1.0 Implementation Tasks

Actionable task list for production release. Execute in order.

---

## Task 1: Data Integrity Scripts

### 1.1 Enhanced Migration Script

```python
# scripts/migrate_json_to_sqlite.py - REPLACE ENTIRE FILE
```

**Requirements:**
- Migrate all JSON conversations to SQLite
- Update message counts after migration
- Generate migration report
- Support --dry-run flag
- Support --verify flag
- Log to file: logs/migration_YYYYMMDD_HHMMSS.log

### 1.2 Data Verification Script

```python
# scripts/verify_data.py - NEW FILE
```

**Requirements:**
- Count conversations in DB vs JSON
- Verify message counts match actual messages
- Check stage1/stage2/stage3 completeness
- Identify orphaned records
- Output report to console and file
- Exit code: 0 = pass, 1 = warnings, 2 = errors

### 1.3 Database Backup Script

```python
# scripts/backup_db.py - NEW FILE
```

**Requirements:**
- Create timestamped backup: backups/council_YYYYMMDD_HHMMSS.db
- Compress with gzip
- Verify backup by opening and checking tables
- Clean up backups older than N days (configurable)
- Support --restore flag

---

## Task 2: Environment Configuration

### 2.1 Create Environment Template

```bash
# .env.example - NEW FILE
```

**Contents:**
```env
# =============================================================================
# LLM Council Configuration
# =============================================================================

# REQUIRED: OpenRouter API Key
# Get yours at: https://openrouter.ai/keys
OPENROUTER_API_KEY=

# =============================================================================
# Council Models (Optional - defaults shown)
# =============================================================================

# Comma-separated list of OpenRouter model identifiers
# COUNCIL_MODELS=anthropic/claude-opus-4,openai/o1,google/gemini-2.5-pro-preview-06-05,x-ai/grok-3-beta,deepseek/deepseek-r1,openai/gpt-4.5,meta-llama/llama-4-maverick,qwen/qwen3-235b-a22b,mistralai/mistral-large-2411

# Model used for final synthesis
# CHAIRMAN_MODEL=anthropic/claude-opus-4

# =============================================================================
# Authentication (Optional)
# =============================================================================

# Set to 'true' to disable authentication (development only!)
# BYPASS_AUTH=false

# =============================================================================
# Rate Limiting (Optional)
# =============================================================================

# RATE_LIMIT_PER_MINUTE=60
# RATE_LIMIT_PER_HOUR=500
# RATE_LIMIT_BURST=10

# =============================================================================
# Database (Optional)
# =============================================================================

# Path to SQLite database file
# DATABASE_PATH=data/council.db

# =============================================================================
# Logging (Optional)
# =============================================================================

# LOG_LEVEL=INFO
# LOG_FORMAT=text  # or 'json' for structured logging

# =============================================================================
# Server (Optional)
# =============================================================================

# HOST=0.0.0.0
# PORT=8001
```

### 2.2 Configuration Loader

```python
# backend/settings.py - NEW FILE
```

**Requirements:**
- Pydantic Settings class
- Load from environment variables
- Load from .env file
- Validate required fields
- Provide defaults for optional fields
- Property for computed values

### 2.3 Startup Validator

```python
# backend/startup.py - NEW FILE
```

**Requirements:**
- Called from main.py before app starts
- Validate OPENROUTER_API_KEY is set
- Validate database is accessible
- Optionally validate OpenRouter connectivity
- Log startup configuration (redact secrets)
- Raise clear errors for missing config

---

## Task 3: Authentication Production

### 3.1 Enhanced Bootstrap Script

```python
# backend/auth/bootstrap.py - REPLACE ENTIRE FILE
```

**Requirements:**
- Check if admin key already exists
- If exists, offer to create additional key or rotate
- Generate secure key
- Display key ONCE with clear warning
- Option to save to file (with secure permissions)
- Support --name, --permissions, --expires flags
- Non-interactive mode for CI/CD

### 3.2 API Key Management CLI

```python
# scripts/manage_keys.py - NEW FILE
```

**Commands:**
- `create` - Create new API key
- `list` - List all keys (prefix only)
- `revoke <id>` - Revoke key by ID
- `status <prefix>` - Check key status
- `audit <id>` - View audit log for key
- `rotate <id>` - Rotate key (create new, revoke old)

**Requirements:**
- Use argparse for CLI
- Pretty output with colors
- JSON output option (--json)
- Confirmation prompts for destructive actions

### 3.3 Enhanced Rate Limiting

```python
# backend/security/rate_limit.py - UPDATE FILE
```

**Requirements:**
- Use API key's custom rate limit if set
- Add X-RateLimit-* headers to responses
- Sliding window algorithm (not fixed window)
- Warn at 80% of limit
- Log rate limit events

---

## Task 4: Docker Production

### 4.1 Production Dockerfile

```dockerfile
# Dockerfile - UPDATE FILE
```

**Requirements:**
- Multi-stage build (frontend + backend)
- Non-root user
- Health check
- Proper signal handling
- Environment variable configuration
- Image size < 500MB

### 4.2 Production Docker Compose

```yaml
# docker-compose.prod.yml - NEW FILE
```

**Requirements:**
- Resource limits
- Restart policy: unless-stopped
- Log rotation
- Named volumes for persistence
- Health check configuration
- Environment file support

### 4.3 Docker Build Test Script

```bash
# scripts/test_docker.sh - NEW FILE
```

**Requirements:**
- Build image
- Run container
- Wait for health check
- Test API endpoints
- Check logs for errors
- Clean up

---

## Task 5: CI/CD Pipeline

### 5.1 CI Workflow Update

```yaml
# .github/workflows/ci.yml - UPDATE FILE
```

**Requirements:**
- Python 3.11 and 3.12
- Cache pip dependencies
- Run linting (ruff)
- Run type checking (mypy)
- Run tests with coverage
- Upload coverage report
- Build Docker image
- Security scan

### 5.2 Release Workflow Update

```yaml
# .github/workflows/release.yml - UPDATE FILE
```

**Requirements:**
- Trigger on version tags
- Build and push Docker image
- Create GitHub release
- Generate changelog
- Upload artifacts

---

## Task 6: Frontend Quality

### 6.1 Frontend Test Configuration

```typescript
// frontend/vitest.config.ts - NEW/UPDATE FILE
```

**Requirements:**
- Configure vitest
- Setup React Testing Library
- Configure coverage
- Setup test utils

### 6.2 Component Tests

**Files to create/update:**
- `frontend/src/components/ChatInterface.test.tsx`
- `frontend/src/components/Stage1.test.tsx`
- `frontend/src/components/Stage2.test.tsx`
- `frontend/src/components/Stage3.test.tsx`
- `frontend/src/components/ConversationList.test.tsx`

**Minimum coverage:**
- Renders without crashing
- Displays data correctly
- Handles loading states
- Handles error states
- User interactions work

### 6.3 API Integration Tests

```typescript
// frontend/src/api.test.ts - NEW FILE
```

**Requirements:**
- Mock fetch/axios
- Test all API functions
- Test error handling
- Test request formatting

---

## Task 7: Documentation

### 7.1 README Update

```markdown
# README.md - UPDATE FILE
```

**Sections:**
- Project description
- Features list
- Quick start
- Configuration
- Development setup
- Deployment
- Contributing
- License

### 7.2 User Guide

```markdown
# docs/USER_GUIDE.md - NEW FILE
```

**Sections:**
- What is LLM Council
- How it works (3-stage process)
- Getting started
- Using the interface
- Understanding results
- Configuration options
- FAQ

### 7.3 API Documentation

```markdown
# docs/API.md - NEW FILE
```

**Sections:**
- Authentication
- Rate limiting
- Endpoints (with examples)
- Error handling
- WebSocket/SSE streams

### 7.4 Deployment Guide

```markdown
# docs/DEPLOYMENT.md - NEW FILE
```

**Sections:**
- Prerequisites
- Docker deployment
- Manual deployment
- Reverse proxy setup
- SSL/TLS
- Monitoring
- Backup/restore
- Troubleshooting

### 7.5 Changelog

```markdown
# CHANGELOG.md - NEW FILE
```

**Format:**
```
## [1.0.0] - YYYY-MM-DD

### Added
- Feature list

### Changed
- Changes list

### Fixed
- Fixes list

### Security
- Security fixes
```

---

## Task 8: Monitoring

### 8.1 Logging Configuration

```python
# backend/logging_config.py - NEW FILE
```

**Requirements:**
- JSON format option
- Request ID tracking
- Configurable levels
- File and console handlers
- Sensitive data redaction
- Correlation IDs

### 8.2 Enhanced Health Endpoints

```python
# backend/health.py - NEW FILE
```

**Endpoints:**
- `GET /health` - Basic liveness (always 200 if running)
- `GET /health/ready` - Readiness (DB connected, etc.)
- `GET /health/detailed` - Full status (requires admin auth)

**Detailed response:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "uptime_seconds": 3600,
  "database": {
    "connected": true,
    "conversations": 42,
    "messages": 156
  },
  "openrouter": {
    "configured": true,
    "last_check": "2024-01-18T12:00:00Z"
  }
}
```

---

## Task 9: Security Hardening

### 9.1 Security Headers Middleware

```python
# backend/security/headers.py - NEW FILE
```

**Headers to add:**
- Content-Security-Policy
- X-Content-Type-Options: nosniff
- X-Frame-Options: DENY
- X-XSS-Protection: 1; mode=block
- Referrer-Policy: strict-origin-when-cross-origin

### 9.2 Input Validation Audit

**Files to review:**
- `backend/main.py` - All endpoint inputs
- `backend/council/` - Prompt construction
- `backend/storage.py` - Database inputs

**Checklist:**
- [ ] All user inputs validated
- [ ] SQL injection prevented (parameterized queries)
- [ ] XSS prevented (content sanitization)
- [ ] Path traversal prevented
- [ ] Size limits enforced

### 9.3 Dependency Audit

```bash
# Run these commands:
pip install safety
safety check

pip install pip-audit
pip-audit
```

**Requirements:**
- No critical vulnerabilities
- Document any accepted risks
- Update vulnerable packages

---

## Task 10: Final Verification

### 10.1 Manual Test Checklist

```markdown
# tests/MANUAL_TEST_CHECKLIST.md - NEW FILE
```

**Test Cases:**
- [ ] Fresh install from README
- [ ] Create conversation
- [ ] Send message, verify 3 stages
- [ ] View conversation history
- [ ] Rename conversation
- [ ] Pin conversation
- [ ] Delete conversation
- [ ] Multiple conversations
- [ ] Streaming responses
- [ ] Model failure handling
- [ ] Rate limiting
- [ ] Authentication (when enabled)

### 10.2 Load Test Script

```python
# scripts/load_test.py - NEW FILE
```

**Requirements:**
- Configurable concurrent users
- Configurable duration
- Report response times
- Report error rates
- Report throughput

### 10.3 Release Script

```bash
# scripts/release.sh - NEW FILE
```

**Steps:**
1. Run all tests
2. Check for uncommitted changes
3. Update version in files
4. Generate changelog
5. Create git tag
6. Push tag
7. Build Docker image
8. Push to registry

---

## Execution Order

Execute tasks in this order for optimal dependency management:

1. **Task 2.1** - Create .env.example (no dependencies)
2. **Task 2.2** - Configuration loader (no dependencies)
3. **Task 2.3** - Startup validator (depends on 2.2)
4. **Task 1.1** - Enhanced migration (no dependencies)
5. **Task 1.2** - Data verification (no dependencies)
6. **Task 1.3** - Database backup (no dependencies)
7. **Task 3.1** - Bootstrap script (depends on 2.2)
8. **Task 3.2** - Key management CLI (depends on 3.1)
9. **Task 3.3** - Rate limiting (depends on 2.2)
10. **Task 8.1** - Logging configuration (depends on 2.2)
11. **Task 8.2** - Health endpoints (depends on 8.1)
12. **Task 9.1** - Security headers (no dependencies)
13. **Task 9.2** - Input validation audit (no dependencies)
14. **Task 9.3** - Dependency audit (no dependencies)
15. **Task 4.1** - Production Dockerfile (depends on all backend)
16. **Task 4.2** - Production compose (depends on 4.1)
17. **Task 4.3** - Docker test script (depends on 4.2)
18. **Task 5.1** - CI workflow (depends on tests)
19. **Task 5.2** - Release workflow (depends on 5.1)
20. **Task 6.1** - Frontend test config (no dependencies)
21. **Task 6.2** - Component tests (depends on 6.1)
22. **Task 6.3** - API tests (depends on 6.1)
23. **Task 7.1-7.5** - Documentation (depends on all features)
24. **Task 10.1** - Manual test checklist (depends on all features)
25. **Task 10.2** - Load test script (depends on all features)
26. **Task 10.3** - Release script (final task)

---

## Verification Commands

After each task, run these commands to verify:

```bash
# Run all tests
python -m pytest backend/tests/ -v

# Check for import errors
python -c "from backend.main import app; print('OK')"

# Check API health
curl http://localhost:8001/health

# Run linting
ruff check backend/

# Run type checking
mypy backend/ --ignore-missing-imports
```
