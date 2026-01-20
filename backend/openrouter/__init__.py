"""
OpenRouter client - async functions for querying LLMs.
"""

from .client import OpenRouterClient
from .config import OpenRouterConfig, RetryConfig, TimeoutConfig, CircuitBreakerConfig
from .circuit_breaker import CircuitBreaker, CircuitState
from .exceptions import (
    OpenRouterError,
    OpenRouterTimeoutError,
    OpenRouterConnectionError,
    RateLimitError,
    ServerError,
    ModelNotFoundError,
    InvalidRequestError,
    CircuitBreakerOpenError,
)
from .legacy import query_model, query_models_parallel, stream_model_response
from .retry import RetryableOperation

__all__ = [
    # New client
    "OpenRouterClient",
    "OpenRouterConfig",
    "RetryConfig",
    "TimeoutConfig",
    "CircuitBreakerConfig",
    # Circuit breaker
    "CircuitBreaker",
    "CircuitState",
    # Exceptions
    "OpenRouterError",
    "OpenRouterTimeoutError",
    "OpenRouterConnectionError",
    "RateLimitError",
    "ServerError",
    "ModelNotFoundError",
    "InvalidRequestError",
    "CircuitBreakerOpenError",
    # Legacy functions
    "query_model",
    "query_models_parallel",
    "stream_model_response",
    # Retry
    "RetryableOperation",
]
