# Technology Stack

This document defines the approved technologies for LLM Council and the evaluation process for new additions.

---

## Current Stack

### Backend

| Technology | Version | Purpose |
|------------|---------|---------|
| Python | 3.10+ | Runtime |
| FastAPI | Latest | Web framework |
| httpx | Latest | Async HTTP client |
| Pydantic | Latest | Data validation |
| uvicorn | Latest | ASGI server |

### Frontend

| Technology | Version | Purpose |
|------------|---------|---------|
| React | 19 | UI framework |
| TypeScript | 5.x | Type safety |
| Vite | Latest | Build tool |
| Zustand | Latest | State management |
| Tailwind CSS | Latest | Styling |
| ReactMarkdown | Latest | Markdown rendering |

### External Services

| Service | Purpose |
|---------|---------|
| OpenRouter | Multi-provider LLM gateway |

### Development Tools

| Tool | Purpose |
|------|---------|
| uv | Python package manager |
| npm | Node package manager |
| VS Code | IDE |

---

## Package Managers

| Language | Manager | Lock File |
|----------|---------|-----------|
| Python | uv | `uv.lock` |
| JavaScript | npm | `package-lock.json` |

---

## Port Assignments

| Service | Port |
|---------|------|
| Frontend (Vite) | 5173 |
| Backend (FastAPI) | 8001 |

---

## Adding New Dependencies

### Evaluation Checklist

Before adding ANY new package:

1. **Check existing tools** — Do we already have something that works?
2. **Verify maintenance** — Last commit < 1 year, issues addressed
3. **Check license** — MIT, Apache 2.0, BSD preferred
4. **Test in isolation** — POC before integration
5. **Update this document** — Add to relevant section

### Red Flags (Avoid)

- Last commit > 1 year ago
- No TypeScript types (for npm packages)
- GPL/LGPL without understanding implications
- Excessive transitive dependencies
- Complex installation requirements

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENROUTER_API_KEY` | Yes | API key for OpenRouter |

Create a `.env` file in project root:
```bash
OPENROUTER_API_KEY=sk-or-v1-your-api-key-here
```

---

## Model Configuration

Default models are defined in `backend/config.py`:

```python
COUNCIL_MODELS = [
    "anthropic/claude-opus-4",
    "openai/o1",
    "google/gemini-2.5-pro-preview-06-05",
    "x-ai/grok-3-beta",
    "deepseek/deepseek-r1",
]

CHAIRMAN_MODEL = "anthropic/claude-opus-4"
```

Available models: [openrouter.ai/models](https://openrouter.ai/models)
