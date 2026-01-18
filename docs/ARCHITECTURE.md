# LLM Council Architecture

This document maps the project structure to the Luxify Architecture patterns.

---

## Rami (Modules)

Isolated modules with clear responsibilities.

### Backend Rami

#### `backend/config.py` — Configuration
- Public API: `COUNCIL_MODELS`, `CHAIRMAN_MODEL`, environment loading
- Responsibility: Centralized configuration management
- Does NOT handle: Runtime logic, API calls

#### `backend/openrouter.py` — LLM Communication
- Public API: `query_model()`, `query_models_parallel()`
- Responsibility: All communication with OpenRouter API
- Does NOT handle: Business logic, response interpretation

#### `backend/council.py` — Deliberation Logic
- Public API: `stage1_collect_responses()`, `stage2_collect_rankings()`, `stage3_synthesize_final()`, `parse_ranking_from_text()`, `calculate_aggregate_rankings()`
- Responsibility: 3-stage deliberation orchestration, anonymization, ranking aggregation
- Does NOT handle: HTTP routing, data persistence

#### `backend/storage.py` — Persistence
- Public API: `save_conversation()`, `load_conversation()`, `list_conversations()`
- Responsibility: JSON file-based conversation storage
- Does NOT handle: Business logic, API communication

### Frontend Rami

#### `frontend/src/store/councilStore.ts` — State Management
- Public API: Zustand store with conversation state, council config
- Responsibility: Client-side state management
- Does NOT handle: API calls, rendering

#### `frontend/src/api.ts` — API Client
- Public API: `sendMessage()`, `getConversations()`, etc.
- Responsibility: HTTP communication with backend
- Does NOT handle: State management, rendering

---

## Grafts (Integration Points)

Explicit connections between modules.

### `backend/main.py` — Backend Orchestrator
- Connects: All backend rami
- Role: FastAPI routing, CORS, request/response handling
- Data flow: HTTP request → council.py → storage.py → HTTP response
- Transformations: JSON serialization, error wrapping

### `frontend/src/App.tsx` — Frontend Orchestrator
- Connects: Store, API client, Layout components
- Role: Application initialization, routing
- Data flow: User action → store → API → store → render

---

## Water (Events & Data Flow)

### Primary Data Flow: Deliberation

```
User Question
    │
    ▼
┌─────────────────────────────────┐
│ Stage 1: Collect Responses      │
│ - Parallel queries to all models│
│ - Returns: {model: response}    │
└─────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────┐
│ Stage 2: Peer Ranking           │
│ - Anonymize as Response A, B... │
│ - Each model ranks all responses│
│ - Parse rankings from text      │
│ - Calculate aggregate rankings  │
└─────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────┐
│ Stage 3: Chairman Synthesis     │
│ - Receives all responses + ranks│
│ - Produces final answer         │
└─────────────────────────────────┘
    │
    ▼
Response to User
```

### Event: Message Submitted
- Payload: `{ conversationId: string, content: string, councilModels?: string[], chairmanModel?: string }`
- Producer: InputComposer component
- Consumer: Backend /api/conversations/{id}/message endpoint

### Event: Deliberation Complete
- Payload: `{ stage1: {...}, stage2: {...}, stage3: {...}, metadata: {...} }`
- Producer: Backend main.py
- Consumer: Frontend store, DeliberationView component

---

## Sap (Boundary Protection)

Input validation and boundary protection.

### API Boundaries

#### `POST /api/conversations/{id}/message`
- Validates: conversation ID format, message content presence
- Rejects: Empty messages, invalid IDs
- Sanitizes: Trims whitespace from message content

#### OpenRouter API Calls
- Validates: API key presence, model identifier format
- Handles: Rate limits, timeout, connection errors
- Fallback: Returns None on failure (graceful degradation)

### Frontend Boundaries

#### InputComposer
- Validates: Non-empty message before submission
- Prevents: Submission while loading

---

## Leaves (Presentation)

Thin presentation layer components.

### Layout Components (`frontend/src/components/layout/`)

#### `AppLayout.tsx`
- Renders: Overall page structure
- Delegates to: ConversationSidebar, main content area

#### `ConversationSidebar.tsx`
- Renders: Conversation list, new conversation button
- Delegates to: Store for data, callbacks for actions

#### `DeliberationView.tsx`
- Renders: 3-stage tabbed interface
- Delegates to: Stage-specific sub-components

#### `CouncilStatusPanel.tsx`
- Renders: Council configuration display/editor
- Delegates to: Store for config state

### Shared Components (`frontend/src/components/shared/`)

#### `InputComposer.tsx`
- Renders: Message input textarea, send button
- Delegates to: Parent callback for submission

#### `MarkdownRenderer.tsx`
- Renders: Markdown content with proper styling
- Delegates to: ReactMarkdown library

#### `CodeBlock.tsx`
- Renders: Syntax-highlighted code blocks
- Delegates to: Syntax highlighting library

---

## Directory Structure

```
llm-council/
├── backend/
│   ├── __init__.py
│   ├── config.py          # Ramus: Configuration
│   ├── openrouter.py      # Ramus: LLM Communication
│   ├── council.py         # Ramus: Deliberation Logic
│   ├── storage.py         # Ramus: Persistence
│   └── main.py            # Graft: Backend Orchestrator
├── frontend/
│   └── src/
│       ├── api.ts         # Ramus: API Client
│       ├── App.tsx        # Graft: Frontend Orchestrator
│       ├── store/
│       │   └── councilStore.ts  # Ramus: State Management
│       ├── components/
│       │   ├── layout/    # Leaves: Layout components
│       │   └── shared/    # Leaves: Reusable components
│       └── types/
│           └── index.ts   # Water: Type definitions
├── data/
│   └── conversations/     # Persistence storage
├── memory-bank/           # Project context
├── docs/                  # Documentation
├── CLAUDE.md              # Technical documentation
├── FOUNDATION.md          # Development practices
├── features.json          # Feature inventory
└── claude-progress.txt    # Session log
```

---

## Integration Notes

### Backend ↔ Frontend Communication
- Protocol: REST over HTTP
- Port: Backend 8001, Frontend 5173
- CORS: Configured for localhost origins
- Format: JSON request/response bodies

### Model Configuration
- Default models: Defined in `backend/config.py`
- Dynamic config: Can be overridden per-request via API
- Chairman: Separate from council, synthesizes final answer

### Data Persistence
- Location: `data/conversations/`
- Format: JSON files, one per conversation
- Metadata: Not persisted (label_to_model, aggregate_rankings)
