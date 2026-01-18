# LLM Council — Project Brief

## Vision

A multi-LLM deliberation system where AI models collaborate through structured discussion to produce higher-quality answers than any single model.

## Core Innovation

**Anonymized Peer Review** — Models evaluate responses without knowing which model produced them, preventing bias and encouraging honest assessment.

## How It Works

```
User Question
    ↓
Stage 1: First Opinions (parallel)
    ↓
Stage 2: Anonymized Peer Review (each model ranks all responses)
    ↓
Stage 3: Chairman Synthesis (final comprehensive answer)
    ↓
Response to User
```

## Goals

1. **Multi-model comparison** — See how different LLMs approach the same question
2. **Quality through deliberation** — Peer review improves answer quality
3. **Transparency** — All raw outputs visible for inspection
4. **Flexibility** — Configurable council membership and chairman

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Python, FastAPI, async httpx |
| Frontend | React 19, TypeScript, Vite, Zustand |
| LLM Gateway | OpenRouter (multi-provider) |
| Storage | JSON files in `data/conversations/` |

## Key Ports

| Service | Port |
|---------|------|
| Backend | 8001 |
| Frontend | 5173 |

## Origin

Vibe-coded by Andrej Karpathy as a Saturday hack to explore multi-LLM deliberation.
