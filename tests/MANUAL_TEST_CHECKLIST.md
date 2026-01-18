# LLM Council Manual Test Checklist

This checklist should be completed before each release to ensure all functionality works correctly.

## Test Environment

- [ ] Fresh clone of repository
- [ ] Environment variables configured (`.env` from `.env.example`)
- [ ] OpenRouter API key is valid and has credits

---

## Installation Tests

### Fresh Install (README)

- [ ] Clone repository
- [ ] Copy `.env.example` to `.env`
- [ ] Add `OPENROUTER_API_KEY`
- [ ] Run `pip install -e .` or `uv pip install -e .`
- [ ] Run `cd frontend && npm install`
- [ ] Backend starts: `python -m backend.main`
- [ ] Frontend starts: `cd frontend && npm run dev`
- [ ] Application loads at http://localhost:5173

### Docker Install

- [ ] Run `docker-compose -f docker-compose.prod.yml build`
- [ ] Run `docker-compose -f docker-compose.prod.yml up -d`
- [ ] Health check passes: `curl http://localhost:8001/health`
- [ ] Application accessible through browser

---

## Core Functionality

### Conversation Management

- [ ] **Create conversation**: Click "New Conversation"
- [ ] **Rename conversation**: Click edit icon, enter new name, press Enter
- [ ] **Pin conversation**: Click pin icon, conversation moves to "Pinned" section
- [ ] **Unpin conversation**: Click pin icon again, conversation moves back
- [ ] **Hide conversation**: Click hide icon, conversation becomes semi-transparent
- [ ] **Show hidden**: Click "Show hidden conversations" in footer
- [ ] **Delete conversation**: Click delete icon, confirm dialog, conversation removed
- [ ] **Multiple conversations**: Create 3+ conversations, verify list updates

### Message Sending

- [ ] **Send simple message**: Type "What is 2+2?" and press Enter
- [ ] **Stage 1 appears**: Individual model responses load
- [ ] **Stage 2 appears**: Peer evaluations load with rankings
- [ ] **Stage 3 appears**: Final synthesis loads (green background)
- [ ] **Conversation saved**: Refresh page, conversation persists

### Three-Stage Deliberation

- [ ] **Stage 1 tabs**: Can switch between different model responses
- [ ] **Stage 2 tabs**: Can switch between different model evaluations
- [ ] **Stage 2 rankings**: Aggregate rankings show at top
- [ ] **Stage 3 synthesis**: Final answer is comprehensive and balanced
- [ ] **Model attribution**: Model names display correctly in each stage

### Streaming (if enabled)

- [ ] **Stage indicators**: Progress shows as stages complete
- [ ] **Real-time updates**: Responses appear incrementally
- [ ] **Completion**: All stages complete without errors

---

## Edge Cases

### Error Handling

- [ ] **Invalid API key**: Set invalid key, verify graceful error message
- [ ] **Network error**: Disconnect network, verify error handling
- [ ] **Model failure**: If one model fails, others should still work
- [ ] **Empty message**: Try sending empty message, verify validation

### Input Validation

- [ ] **Long message**: Send very long message (1000+ characters)
- [ ] **Special characters**: Send message with `<script>`, `'`, `"`
- [ ] **Unicode**: Send message with emojis and non-ASCII characters
- [ ] **Markdown**: Send message with markdown formatting

### Conversation Edge Cases

- [ ] **Many messages**: Send 10+ messages in one conversation
- [ ] **Empty conversation**: Delete all messages, verify behavior
- [ ] **Rapid clicking**: Click buttons rapidly, verify no race conditions

---

## Authentication (Production Mode)

### API Key Management

- [ ] **Create key**: `python -m backend.auth.bootstrap --name "Test"`
- [ ] **List keys**: `python scripts/manage_keys.py list`
- [ ] **Test key**: API request with key succeeds
- [ ] **Invalid key**: API request with wrong key returns 401
- [ ] **Revoke key**: `python scripts/manage_keys.py revoke <id>`
- [ ] **Revoked key fails**: API request with revoked key returns 401

### Rate Limiting

- [ ] **Normal usage**: Requests succeed within limits
- [ ] **Rate limit headers**: Response includes `X-RateLimit-*` headers
- [ ] **Exceed limit**: Rapid requests return 429 error
- [ ] **Recovery**: Wait and verify requests succeed again

---

## Data Management

### Database

- [ ] **Verify data**: `python scripts/verify_data.py`
- [ ] **No errors**: Verification passes without errors
- [ ] **Create backup**: `python scripts/backup_db.py`
- [ ] **Backup created**: File exists in `backups/` directory
- [ ] **Verify backup**: `python scripts/backup_db.py --verify <backup_file>`

### Migration (if applicable)

- [ ] **Dry run**: `python scripts/migrate_json_to_sqlite.py --dry-run`
- [ ] **Migrate**: `python scripts/migrate_json_to_sqlite.py --verify`
- [ ] **Data preserved**: All conversations appear after migration

---

## UI/UX

### Responsiveness

- [ ] **Desktop**: UI displays correctly at 1920x1080
- [ ] **Tablet**: UI displays correctly at 768px width
- [ ] **Mobile**: UI displays correctly at 375px width
- [ ] **Sidebar collapse**: Sidebar can be collapsed/expanded

### Visual

- [ ] **Loading states**: Loading indicators show during API calls
- [ ] **Error states**: Errors display with clear messages
- [ ] **Dark/Light theme**: Theme displays correctly (if applicable)
- [ ] **Markdown rendering**: Code blocks, links, lists render properly

### Accessibility

- [ ] **Keyboard navigation**: Can navigate with Tab key
- [ ] **Screen reader**: Labels are meaningful (spot check)
- [ ] **Focus indicators**: Focused elements are visible

---

## Performance

### Response Times

- [ ] **Initial load**: < 3 seconds
- [ ] **Message send**: Response starts within 5 seconds
- [ ] **Full deliberation**: Completes within 60 seconds
- [ ] **Conversation load**: < 1 second for normal-sized conversations

### Resource Usage

- [ ] **Memory**: Backend doesn't leak memory over time
- [ ] **CPU**: CPU usage returns to baseline after request
- [ ] **Database**: Database file doesn't grow excessively

---

## Security

### Headers

- [ ] **CSP header**: Present in response
- [ ] **X-Frame-Options**: Present and set to DENY
- [ ] **X-Content-Type-Options**: Present and set to nosniff

### Input Sanitization

- [ ] **XSS attempt**: `<script>alert(1)</script>` is escaped
- [ ] **SQL injection**: `'; DROP TABLE conversations;--` doesn't break anything

---

## Documentation

### Verification

- [ ] **README**: Instructions are accurate
- [ ] **API docs**: Endpoints match actual API
- [ ] **User guide**: Instructions work as described

---

## Sign-off

| Test Category | Tester | Date | Pass/Fail |
|---------------|--------|------|-----------|
| Installation | | | |
| Core Functionality | | | |
| Edge Cases | | | |
| Authentication | | | |
| Data Management | | | |
| UI/UX | | | |
| Performance | | | |
| Security | | | |
| Documentation | | | |

### Notes

_Add any issues found or notes about the testing session:_

---

### Release Decision

- [ ] **All critical tests pass**
- [ ] **No blocking issues**
- [ ] **Ready for release**

Approved by: _________________ Date: _____________
