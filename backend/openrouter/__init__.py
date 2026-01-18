"""
OpenRouter client package.

Provides a robust HTTP client for the OpenRouter API with:
- Retry with exponential backoff
- Circuit breaker pattern
- Rate limit handling
- Comprehensive error classification
"""

from .circuit_breaker import CircuitBreaker, CircuitState, CircuitStats
from .client import OpenRouterClient
from .config import (
    CircuitBreakerConfig,
    OpenRouterConfig,
    RetryConfig,
    TimeoutConfig,
)
from .exceptions import (
    CircuitBreakerOpenError,
    InvalidRequestError,
    ModelNotFoundError,
    OpenRouterConnectionError,
    OpenRouterError,
    OpenRouterTimeoutError,
    RateLimitError,
    ServerError,
)
from .retry import RetryableOperation, calculate_delay, with_retry

# Legacy functions for backwards compatibility with existing code
from .legacy import query_model, query_models_parallel, stream_model_response

__all__ = [
    # Legacy functions (backwards compatibility)
    "query_model",
    "query_models_parallel",
    "stream_model_response",
    # Client
    "OpenRouterClient",
    # Config
    "OpenRouterConfig",
    "RetryConfig",
    "CircuitBreakerConfig",
    "TimeoutConfig",
    # Circuit breaker
    "CircuitBreaker",
    "CircuitState",
    "CircuitStats",
    # Retry
    "with_retry",
    "calculate_delay",
    "RetryableOperation",
    # Exceptions
    "OpenRouterError",
    "RateLimitError",
    "ModelNotFoundError",
    "InvalidRequestError",
    "ServerError",
    "OpenRouterConnectionError",
    "OpenRouterTimeoutError",
    "CircuitBreakerOpenError",
]
