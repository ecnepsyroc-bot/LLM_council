# Progress Log

## 2026-01-17

### Documentation Improvements
- Restored project from OneDrive backup to `C:\dev\llm-council`
- Created `memory-bank/` folder structure (Cambium pattern)
- Created `docs/` folder with TECH-STACK.md
- Added Architecture Decision Record for OpenRouter

---

## 2025-12-05

### Foundation Setup
- Added `FOUNDATION.md` — Development patterns document
- Scaffolded supporting files:
  - `init.sh` — Environment bootstrapping
  - `claude-progress.txt` — Session tracking
  - `features.json` — Feature inventory
  - `.architecture.md` — Structure documentation

### Dynamic Council Configuration
- Implemented configurable council per-request (commit 419184f)
- Frontend can now override default council models
- Backend accepts `councilModels` and `chairmanModel` in message payload

### Previous Work
- Migrated frontend to TypeScript (commit 8625779)
- Added root orchestration scripts (`npm run dev`, etc.)

---

## Known Technical Debt

| Item | Status | Notes |
|------|--------|-------|
| Uncommitted changes | Pending | backend/main.py, storage.py, frontend |
| start.ps1 untracked | Pending | Windows startup script |
| Dynamic config untested | Pending | End-to-end verification needed |

---

## Architecture Notes

- Backend: FastAPI on port 8001
- Frontend: React + TypeScript + Vite on port 5173
- 3-stage deliberation: collect → anonymized review → synthesis
- Data stored in `data/conversations/` as JSON
- Follows Luxify Architecture patterns (rami, grafts, water, sap, leaves)
