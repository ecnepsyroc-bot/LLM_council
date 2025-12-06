# Project Development Foundation

**Version:** 1.0
**Purpose:** Establish patterns for incremental, context-aware development across multiple work sessions

---

## Overview

This document defines the foundational practices for software development in this environment. It addresses the reality that complex work happens across multiple sessions, each potentially starting with limited context. The patterns here ensure every session can:

1. Quickly understand the current state
2. Make meaningful incremental progress
3. Leave the environment ready for the next session

---

## Architecture Alignment

This project follows the **Luxify Architecture**:
- **rami** — isolated modules with clear responsibilities
- **grafts** — explicit integration points between modules
- **water** — event and data flow definitions
- **sap** — input validation and boundary protection
- **leaves** — presentation layer

All development work should respect these boundaries and document connections explicitly.

---

## Initial Environment Setup

Every project must establish these foundational elements on first initialization:

### 1. `init.sh` — Environment Bootstrapping
```bash
#!/bin/bash
# Purpose: Start the development environment from scratch
# Usage: ./init.sh

# Install dependencies
# Start development servers
# Run basic smoke tests
# Output: "Environment ready" or clear error messages
```

### 2. `claude-progress.txt` — Session Log
```
=== PROGRESS LOG ===
Last updated: [timestamp]
Current focus: [active work area]

RECENT SESSIONS:
- [date/time]: [what was accomplished]
- [date/time]: [what was accomplished]

KNOWN ISSUES:
- [issue description and status]

NEXT PRIORITIES:
1. [next logical task]
2. [subsequent task]
```

### 3. `features.json` — Feature Inventory
```json
{
  "features": [
    {
      "id": "F001",
      "category": "functional",
      "description": "User can [action] and [outcome]",
      "dependencies": ["F000"],
      "steps": [
        "Step 1 description",
        "Step 2 description"
      ],
      "passes": false,
      "lastTested": null,
      "notes": ""
    }
  ]
}
```

### 4. `.architecture.md` — Structure Documentation
```markdown
# Project Architecture

## Rami (Modules)
- `rami/[name]/` — [responsibility]
  - Public API: [methods]
  - Does NOT handle: [non-responsibilities]

## Grafts (Integration Points)
- `grafts/[name]/` — Connects [ramus A] to [ramus B]
  - Data flow: [description]
  - Transformations: [what changes]

## Water (Events)
- Event: `[event-name]`
  - Payload: `{ ... }`
  - Producers: [who emits]
  - Consumers: [who listens]
```

### 5. Git Repository
```bash
# Initial commit establishes baseline
git init
git add .
git commit -m "Initial project structure"
```

---

## Session Workflow

Every work session follows this pattern:

### Starting a Session

```bash
# 1. Confirm working directory
pwd

# 2. Review recent history
git log --oneline -20
cat claude-progress.txt

# 3. Understand current state
cat features.json | grep -A 5 '"passes": false'

# 4. Verify environment
./init.sh  # Should complete without errors

# 5. Run smoke test
# [project-specific basic functionality test]
```

**Before starting new work, always verify the app still works.**

### During a Session

**One Feature at a Time**
- Choose a single feature from `features.json` with `"passes": false`
- Work only on that feature until it passes all tests
- Do not start additional features until current one is complete

**Testing Requirements**
- Test as an end user would test
- Use browser automation for web apps
- Use appropriate testing tools for the domain
- Verify the feature works end-to-end, not just in isolation
- Only mark `"passes": true` after successful testing

**Documentation as You Go**
- Update `.architecture.md` when structure changes
- Add comments for non-obvious decisions
- Keep `features.json` current

### Ending a Session

```bash
# 1. Ensure clean state
# - No syntax errors
# - No half-implemented features
# - App runs without critical bugs

# 2. Update feature status
# Edit features.json to mark completed features

# 3. Commit progress
git add -A
git commit -m "Feat: [clear description of what was accomplished]

- Completed feature F001: [description]
- Updated [affected areas]
- Tests: [what was verified]"

# 4. Update progress log
cat >> claude-progress.txt << EOF

=== [timestamp] ===
COMPLETED: Feature F001 - [description]
TESTED: [how it was verified]
NEXT: Feature F002 - [what should be done next]
NOTES: [any issues, decisions, or context for next session]
EOF

# 5. Verify clean state
./init.sh && [run smoke test]
```

---

## Development Principles

### Incremental Progress
- **Never** try to implement multiple features in one session
- **Always** leave the codebase in a working state
- **Prefer** smaller, complete changes over larger, incomplete ones

### Clean State Definition
A "clean state" means:
- ✅ Code runs without critical errors
- ✅ Recent changes are tested and working
- ✅ Git commit describes what was done
- ✅ Progress log explains current status
- ✅ No half-implemented features
- ✅ Documentation reflects current reality

### Architectural Discipline
- **Rami never import from other rami** — use grafts
- **Grafts never contain domain logic** — orchestrate only
- **Water is declarative** — no implementation
- **Sap protects boundaries** — validate, don't transform
- **Leaves remain thin** — delegate to grafts

### Testing Standards
- Test from the user's perspective
- Use appropriate automation tools
- Verify end-to-end workflows
- Don't mark features complete until proven working
- Document test procedures in feature entries

---

## Feature Management

### Feature Definition Standards
Each feature must have:
1. **Clear description** — "User can [action] and [outcome]"
2. **Testable steps** — Specific actions to verify
3. **Dependencies** — What must work first
4. **Category** — functional, performance, security, etc.

### Feature Lifecycle
```
[Planned] → [In Progress] → [Testing] → [Passes]
                ↓
           [Blocked/Issues]
```

### Priority Rules
1. Unblock blocked features first
2. Complete partial implementations before starting new work
3. Fix broken tests before adding new features
4. Respect dependency chains (build F001 before F002 if F002 depends on F001)

---

## Error Recovery

### If Previous Session Left Broken Code
```bash
# 1. Review what happened
git log -1 --stat
cat claude-progress.txt

# 2. Assess damage
./init.sh  # Does it fail?
[run smoke test]

# 3. Decide: fix or revert
git diff  # Small issue? Fix it.
git reset --hard HEAD~1  # Bigger issue? Revert and redo properly.

# 4. Document
cat >> claude-progress.txt << EOF
[timestamp]: Recovered from broken state
Previous session left [issue description]
Action taken: [fix or revert]
EOF
```

---

## Evolution Guidelines

### When to Split a Ramus
- Responsibilities become unclear
- File count exceeds 15-20 files
- Multiple unrelated concerns mixed together
- Module needs to be reused independently

### When to Add a Graft
- Two rami need to communicate
- Data flows between modules
- Orchestration logic is needed
- Integration point becomes complex

### When to Update Architecture Docs
- Every time structure changes
- When adding new rami/grafts
- When modifying public APIs
- When changing data flows

---

## Prohibited Practices

**Never:**
- Remove or edit features from `features.json` (only change `passes` status)
- Mark features as passing without proper testing
- Leave uncommitted changes at session end
- Start new features with existing broken tests
- Implement multiple features simultaneously
- Import rami from other rami directly
- Put domain logic in grafts
- Leave progress log outdated

---

## Quick Reference

### Session Start Checklist
- [ ] Confirm working directory
- [ ] Read git log (last 20 commits)
- [ ] Read claude-progress.txt
- [ ] Check features.json for current status
- [ ] Run init.sh successfully
- [ ] Verify basic functionality works
- [ ] Choose one feature to work on

### Session End Checklist
- [ ] Code runs without errors
- [ ] Feature is fully tested
- [ ] features.json updated
- [ ] Git commit with clear message
- [ ] claude-progress.txt updated
- [ ] Smoke test passes
- [ ] Next steps documented

---

**This document should be referenced at the start of every development session.**
