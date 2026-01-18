"""Configuration for OpenRouter client."""

import os
from dataclasses import dataclass, field
from typing import Dict, Tuple


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    max_retries: int = 3
    initial_delay: float = 1.0  # Initial delay in seconds
    max_delay: float = 60.0  # Maximum delay in seconds
    exponential_base: float = 2.0  # Exponential backoff base
    jitter: bool = True  # Add random jitter to delays

    # Which status codes to retry
    retryable_status_codes: Tuple[int, ...] = (408, 429, 500, 502, 503, 504)


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""

    failure_threshold: int = 5  # Failures before opening circuit
    success_threshold: int = 2  # Successes before closing circuit
    timeout: float = 60.0  # Time to wait before half-open state

    # Track per-model or global
    per_model: bool = True


@dataclass
class TimeoutConfig:
    """Configuration for request timeouts."""

    connect_timeout: float = 10.0  # Time to establish connection
    read_timeout: float = 120.0  # Time to receive response

    # Per-model timeout overrides
    model_timeouts: Dict[str, Tuple[float, float]] = field(default_factory=dict)

    def get_timeout(self, model: str) -> Tuple[float, float]:
        """Get timeout for a specific model."""
        if model in self.model_timeouts:
            return self.model_timeouts[model]
        return (self.connect_timeout, self.read_timeout)


@dataclass
class OpenRouterConfig:
    """Complete configuration for OpenRouter client."""

    api_key: str = field(
        default_factory=lambda: os.getenv("OPENROUTER_API_KEY", "")
    )
    base_url: str = "https://openrouter.ai/api/v1"

    retry: RetryConfig = field(default_factory=RetryConfig)
    circuit_breaker: CircuitBreakerConfig = field(default_factory=CircuitBreakerConfig)
    timeout: TimeoutConfig = field(default_factory=TimeoutConfig)

    # Request defaults
    default_temperature: float = 0.7
    default_max_tokens: int = 4096

    # Logging
    log_requests: bool = True
    log_responses: bool = False  # Can be verbose

    def __post_init__(self):
        # Allow empty API key for testing
        pass
