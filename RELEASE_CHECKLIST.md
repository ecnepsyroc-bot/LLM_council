# LLM Council v1.0 Release Checklist

This document outlines all tasks required to bring LLM Council to production-ready status.

---

## Current State Assessment

### Completed ✅
- [x] SQLite database with proper schema
- [x] Authentication system (API keys, permissions, audit logging)
- [x] OpenRouter client hardening (retry, circuit breaker, rate limiting)
- [x] Streaming event types for granular status updates
- [x] Model configuration and validation framework
- [x] Council refactored into modular packages
- [x] 149 backend tests passing
- [x] Docker and CI/CD scaffolding
- [x] Port registry and dev scripts

### Incomplete ❌
- [ ] Data integrity (message counts, migration verification)
- [ ] Production environment configuration
- [ ] API key bootstrap for production
- [ ] Docker build verification
- [ ] CI/CD pipeline testing
- [ ] Frontend tests
- [ ] Documentation
- [ ] Monitoring and observability

---

## Phase 1: Data Integrity

### 1.1 Migration Script Enhancement
**File:** `scripts/migrate_json_to_sqlite.py`

Current migration imports conversations but has issues:
- Message counts not updated after migration
- No verification step
- No rollback capability

**Tasks:**
- [ ] Add post-migration message count update
- [ ] Add verification report
- [ ] Add dry-run mode
- [ ] Add rollback capability
- [ ] Log migration details to file

### 1.2 Data Verification Script
**File:** `scripts/verify_data.py`

Create script to verify data integrity:
- [ ] Check all conversations have valid IDs
- [ ] Verify message counts match actual messages
- [ ] Verify stage1/stage2/stage3 data exists for assistant messages
- [ ] Check for orphaned records
- [ ] Generate integrity report

### 1.3 Database Backup Script
**File:** `scripts/backup_db.py`

- [ ] Create timestamped SQLite backup
- [ ] Compress backup files
- [ ] Configurable retention policy
- [ ] Verify backup integrity

---

## Phase 2: Environment Configuration

### 2.1 Environment Template
**File:** `.env.example`

```env
# Required
OPENROUTER_API_KEY=your_openrouter_api_key_here

# Optional - Council Configuration
COUNCIL_MODELS=anthropic/claude-opus-4,openai/o1,google/gemini-2.5-pro-preview-06-05
CHAIRMAN_MODEL=anthropic/claude-opus-4

# Optional - Authentication
BYPASS_AUTH=false
ADMIN_API_KEY_NAME=admin

# Optional - Rate Limiting
RATE_LIMIT_PER_MINUTE=60
RATE_LIMIT_PER_HOUR=500

# Optional - Database
DATABASE_PATH=data/council.db

# Optional - Logging
LOG_LEVEL=INFO
LOG_FORMAT=json
```

### 2.2 Configuration Module Enhancement
**File:** `backend/config/__init__.py`

- [ ] Load all settings from environment
- [ ] Validate required settings on startup
- [ ] Provide sensible defaults
- [ ] Support for config file override

### 2.3 Startup Validation
**File:** `backend/startup.py`

Create startup validation that:
- [ ] Checks all required environment variables
- [ ] Validates OpenRouter API key
- [ ] Validates database connection
- [ ] Logs configuration summary (without secrets)
- [ ] Fails fast with clear error messages

---

## Phase 3: Authentication Production Setup

### 3.1 Bootstrap Script Enhancement
**File:** `backend/auth/bootstrap.py`

Current script creates admin key but needs:
- [ ] Check if admin key already exists
- [ ] Support for key rotation
- [ ] Secure output (don't log full key)
- [ ] Save key to secure location option
- [ ] Interactive and non-interactive modes

### 3.2 API Key Management CLI
**File:** `scripts/manage_keys.py`

Create CLI tool for:
- [ ] Create new API key
- [ ] List all keys (without secrets)
- [ ] Revoke key by ID or prefix
- [ ] Check key status
- [ ] View audit log for key

### 3.3 Rate Limiting Enhancement
**File:** `backend/security/rate_limit.py`

- [ ] Per-key rate limiting (use key's custom limit)
- [ ] Sliding window algorithm
- [ ] Rate limit headers in responses
- [ ] Configurable warning threshold

---

## Phase 4: Docker Production Build

### 4.1 Dockerfile Verification
**File:** `Dockerfile`

- [ ] Test multi-stage build completes
- [ ] Verify image size is reasonable (<500MB)
- [ ] Ensure non-root user works
- [ ] Test health check endpoint
- [ ] Verify static files are served correctly

### 4.2 Docker Compose Production Config
**File:** `docker-compose.prod.yml`

Create production-specific compose file:
- [ ] Resource limits (CPU, memory)
- [ ] Restart policies
- [ ] Log configuration
- [ ] Volume mounts for data persistence
- [ ] Network configuration

### 4.3 Container Security Scan
- [ ] Run Trivy or similar scanner
- [ ] Address critical/high vulnerabilities
- [ ] Document accepted risks

---

## Phase 5: CI/CD Pipeline

### 5.1 CI Pipeline Verification
**File:** `.github/workflows/ci.yml`

- [ ] Test workflow runs successfully
- [ ] All test jobs pass
- [ ] Coverage reporting works
- [ ] Docker build job completes
- [ ] Security scan job runs

### 5.2 Release Workflow Enhancement
**File:** `.github/workflows/release.yml`

- [ ] Test tag-triggered release
- [ ] Verify image pushed to registry
- [ ] Release notes generation works
- [ ] Add changelog generation

### 5.3 Branch Protection
- [ ] Require PR reviews
- [ ] Require CI passing
- [ ] Require up-to-date branches

---

## Phase 6: Frontend Quality

### 6.1 Frontend Test Suite
**Files:** `frontend/src/**/*.test.tsx`

- [ ] Verify existing tests run
- [ ] Add missing component tests
- [ ] Add integration tests for API calls
- [ ] Achieve >70% coverage

### 6.2 Frontend Build Verification
- [ ] Production build completes without warnings
- [ ] Bundle size is reasonable (<1MB)
- [ ] No console errors in production build
- [ ] Assets load correctly

### 6.3 Accessibility Audit
- [ ] Run axe or lighthouse audit
- [ ] Fix critical accessibility issues
- [ ] Document known limitations

---

## Phase 7: Documentation

### 7.1 User Documentation
**File:** `docs/USER_GUIDE.md`

- [ ] Installation instructions
- [ ] Configuration guide
- [ ] Usage examples
- [ ] Troubleshooting guide

### 7.2 API Documentation
**File:** `docs/API.md`

- [ ] All endpoints documented
- [ ] Request/response examples
- [ ] Authentication guide
- [ ] Error codes and handling

### 7.3 Deployment Guide
**File:** `docs/DEPLOYMENT.md`

- [ ] Docker deployment steps
- [ ] Environment configuration
- [ ] Reverse proxy setup (nginx/caddy)
- [ ] SSL/TLS configuration
- [ ] Backup and restore procedures

### 7.4 Development Guide
**File:** `docs/DEVELOPMENT.md`

- [ ] Local setup instructions
- [ ] Architecture overview
- [ ] Contributing guidelines
- [ ] Code style guide

### 7.5 Changelog
**File:** `CHANGELOG.md`

- [ ] Document all features
- [ ] List breaking changes
- [ ] Credit contributors

---

## Phase 8: Monitoring and Observability

### 8.1 Structured Logging
**File:** `backend/logging_config.py`

- [ ] JSON log format option
- [ ] Request ID in all logs
- [ ] Log levels configurable
- [ ] Sensitive data redaction

### 8.2 Health Endpoints
**File:** `backend/main.py`

Enhance health endpoint:
- [ ] `/health` - basic liveness
- [ ] `/health/ready` - readiness (DB connected, etc.)
- [ ] `/health/detailed` - full status (admin only)

### 8.3 Metrics (Optional)
**File:** `backend/metrics.py`

If needed:
- [ ] Request count/latency
- [ ] Error rates
- [ ] OpenRouter API metrics
- [ ] Prometheus format export

---

## Phase 9: Security Hardening

### 9.1 Security Headers
**File:** `backend/security/headers.py`

Add middleware for:
- [ ] Content-Security-Policy
- [ ] X-Content-Type-Options
- [ ] X-Frame-Options
- [ ] Strict-Transport-Security (when behind HTTPS)

### 9.2 Input Validation Audit
- [ ] Review all user inputs
- [ ] Ensure proper sanitization
- [ ] Check for injection vulnerabilities

### 9.3 Dependency Audit
- [ ] Run `pip audit` or `safety check`
- [ ] Update vulnerable dependencies
- [ ] Document any accepted risks

### 9.4 Secret Management
- [ ] No secrets in code or config files
- [ ] Environment variables for all secrets
- [ ] Document secret rotation procedure

---

## Phase 10: Final Verification

### 10.1 End-to-End Testing
Manual testing checklist:
- [ ] Create new conversation
- [ ] Send message, verify 3-stage deliberation
- [ ] View conversation history
- [ ] Delete conversation
- [ ] Test with multiple council models
- [ ] Test streaming responses
- [ ] Test error handling (model failure)

### 10.2 Performance Testing
- [ ] Response time under normal load
- [ ] Behavior under high load
- [ ] Memory usage over time
- [ ] Database size growth

### 10.3 Release Candidate
- [ ] Tag RC version
- [ ] Deploy to staging
- [ ] 24-hour soak test
- [ ] Final review

### 10.4 Release
- [ ] Tag v1.0.0
- [ ] Push Docker image
- [ ] Update documentation
- [ ] Announce release

---

## Priority Order

### Critical (Must Have)
1. Data integrity verification
2. Environment configuration
3. Authentication bootstrap
4. Docker build verification
5. Basic documentation

### Important (Should Have)
6. CI/CD verification
7. Frontend tests
8. Security hardening
9. Structured logging

### Nice to Have
10. Metrics/monitoring
11. Advanced documentation
12. Performance testing

---

## Estimated Effort

| Phase | Effort | Priority |
|-------|--------|----------|
| 1. Data Integrity | 2-3 hours | Critical |
| 2. Environment Config | 1-2 hours | Critical |
| 3. Auth Production | 2-3 hours | Critical |
| 4. Docker Production | 2-3 hours | Critical |
| 5. CI/CD Pipeline | 1-2 hours | Important |
| 6. Frontend Quality | 3-4 hours | Important |
| 7. Documentation | 4-6 hours | Critical |
| 8. Monitoring | 2-3 hours | Important |
| 9. Security | 2-3 hours | Important |
| 10. Final Verification | 2-3 hours | Critical |

**Total: ~25-35 hours**

---

## Sign-off

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Developer | | | |
| Reviewer | | | |
| Release Manager | | | |
