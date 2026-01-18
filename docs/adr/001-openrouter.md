# ADR 001: Use OpenRouter as LLM Gateway

**Status:** Accepted  
**Date:** 2025

---

## Context

LLM Council needs to query multiple LLM providers (OpenAI, Anthropic, Google, etc.) to enable multi-model deliberation. Options considered:

1. **Direct integration** — Separate SDK for each provider
2. **OpenRouter** — Unified gateway to multiple providers
3. **LiteLLM** — Open-source proxy

---

## Decision

Use **OpenRouter** as the unified LLM gateway.

---

## Rationale

| Factor | OpenRouter | Direct | LiteLLM |
|--------|------------|--------|---------|
| Single API key | ✅ Yes | ❌ No | ✅ Yes |
| Provider availability | ✅ 100+ models | ❌ Per-provider | ✅ Good |
| Self-hosting required | ❌ No | ❌ No | ✅ Yes |
| Maintenance burden | Low | High | Medium |
| Pricing transparency | ✅ Clear | ✅ Clear | ✅ Clear |

OpenRouter provides the best balance of simplicity and model availability with minimal maintenance overhead.

---

## Consequences

### Positive
- Single API key manages all providers
- Easy to add/remove models via config
- Consistent API format across providers
- No infrastructure to maintain

### Negative
- Dependent on OpenRouter availability
- Slight latency overhead
- Usage costs (though pass-through pricing)

---

## Implementation

All LLM calls go through `backend/openrouter.py`:

```python
from .config import OPENROUTER_API_KEY

async def query_model(model: str, prompt: str) -> dict:
    # Calls OpenRouter API
    ...
```

Model identifiers follow OpenRouter format: `provider/model-name`

---

## Review Triggers

Reconsider this decision if:
- OpenRouter has extended downtime (>24h)
- A critical model becomes unavailable on OpenRouter
- Self-hosting becomes a requirement
