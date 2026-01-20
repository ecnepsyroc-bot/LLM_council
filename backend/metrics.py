"""Prometheus metrics for LLM Council."""

import time
from functools import wraps
from typing import Callable

from prometheus_client import Counter, Gauge, Histogram, Info, generate_latest, CONTENT_TYPE_LATEST
from fastapi import APIRouter, Response

# Application info
APP_INFO = Info("llm_council", "LLM Council application information")
APP_INFO.info({
    "version": "1.0.0",
    "service": "llm-council"
})

# Request metrics
REQUEST_COUNT = Counter(
    "llm_council_requests_total",
    "Total number of requests",
    ["method", "endpoint", "status"]
)

REQUEST_LATENCY = Histogram(
    "llm_council_request_latency_seconds",
    "Request latency in seconds",
    ["method", "endpoint"],
    buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0)
)

# Deliberation metrics
DELIBERATION_COUNT = Counter(
    "llm_council_deliberations_total",
    "Total number of deliberations",
    ["status"]  # success, error
)

DELIBERATION_LATENCY = Histogram(
    "llm_council_deliberation_latency_seconds",
    "Deliberation latency in seconds",
    ["stage"],  # stage1, stage2, stage3, total
    buckets=(1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0)
)

# Model metrics
MODEL_QUERY_COUNT = Counter(
    "llm_council_model_queries_total",
    "Total number of model queries",
    ["model", "status"]  # status: success, error, timeout
)

MODEL_QUERY_LATENCY = Histogram(
    "llm_council_model_query_latency_seconds",
    "Model query latency in seconds",
    ["model"],
    buckets=(0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0)
)

# Circuit breaker metrics
CIRCUIT_BREAKER_STATE = Gauge(
    "llm_council_circuit_breaker_state",
    "Circuit breaker state (0=closed, 1=open, 2=half_open)",
    ["model"]
)

CIRCUIT_BREAKER_FAILURES = Counter(
    "llm_council_circuit_breaker_failures_total",
    "Total circuit breaker failures",
    ["model"]
)

# Conversation metrics
CONVERSATIONS_ACTIVE = Gauge(
    "llm_council_conversations_active",
    "Number of active conversations"
)

MESSAGES_TOTAL = Counter(
    "llm_council_messages_total",
    "Total number of messages",
    ["role"]  # user, assistant
)

# Rate limiting metrics
RATE_LIMIT_HITS = Counter(
    "llm_council_rate_limit_hits_total",
    "Number of rate limit hits",
    ["key_prefix"]
)

# Token usage metrics
TOKEN_USAGE = Counter(
    "llm_council_tokens_total",
    "Total token usage",
    ["model", "type"]  # type: prompt, completion
)

# Security metrics
INJECTION_ATTEMPTS = Counter(
    "llm_council_injection_attempts_total",
    "Total prompt injection attempts detected",
    ["pattern_type"]  # instruction_override, role_manipulation, etc.
)

PII_DETECTIONS = Counter(
    "llm_council_pii_detections_total",
    "Total PII detections in responses",
    ["pii_type"]  # ssn, credit_card, email, etc.
)


def track_request(method: str, endpoint: str) -> Callable:
    """Decorator to track request metrics."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            status = "success"
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                status = "error"
                raise
            finally:
                latency = time.time() - start_time
                REQUEST_COUNT.labels(method=method, endpoint=endpoint, status=status).inc()
                REQUEST_LATENCY.labels(method=method, endpoint=endpoint).observe(latency)
        return wrapper
    return decorator


def track_deliberation_stage(stage: str) -> Callable:
    """Decorator to track deliberation stage latency."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                latency = time.time() - start_time
                DELIBERATION_LATENCY.labels(stage=stage).observe(latency)
        return wrapper
    return decorator


def record_model_query(model: str, status: str, latency: float):
    """Record a model query."""
    MODEL_QUERY_COUNT.labels(model=model, status=status).inc()
    MODEL_QUERY_LATENCY.labels(model=model).observe(latency)


def record_circuit_breaker_state(model: str, state: int):
    """Record circuit breaker state (0=closed, 1=open, 2=half_open)."""
    CIRCUIT_BREAKER_STATE.labels(model=model).set(state)


def record_circuit_breaker_failure(model: str):
    """Record a circuit breaker failure."""
    CIRCUIT_BREAKER_FAILURES.labels(model=model).inc()


def record_message(role: str):
    """Record a message."""
    MESSAGES_TOTAL.labels(role=role).inc()


def set_active_conversations(count: int):
    """Set the number of active conversations."""
    CONVERSATIONS_ACTIVE.set(count)


def record_rate_limit_hit(key_prefix: str):
    """Record a rate limit hit."""
    RATE_LIMIT_HITS.labels(key_prefix=key_prefix).inc()


def record_token_usage(model: str, prompt_tokens: int, completion_tokens: int):
    """Record token usage for a model query."""
    TOKEN_USAGE.labels(model=model, type="prompt").inc(prompt_tokens)
    TOKEN_USAGE.labels(model=model, type="completion").inc(completion_tokens)


def record_injection_attempt(pattern_type: str):
    """Record a prompt injection attempt detection."""
    INJECTION_ATTEMPTS.labels(pattern_type=pattern_type).inc()


def record_pii_detection(pii_type: str):
    """Record a PII detection in response."""
    PII_DETECTIONS.labels(pii_type=pii_type).inc()


# Metrics endpoint
router = APIRouter(tags=["Metrics"])


@router.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )
