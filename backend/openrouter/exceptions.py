"""Custom exceptions for OpenRouter client."""

from typing import Optional


class OpenRouterError(Exception):
    """Base exception for OpenRouter errors."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        retry_after: Optional[int] = None,
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.retry_after = retry_after


class RateLimitError(OpenRouterError):
    """Raised when rate limit is exceeded."""

    def __init__(self, retry_after: int = 60):
        super().__init__(
            f"Rate limit exceeded. Retry after {retry_after} seconds.",
            status_code=429,
            retry_after=retry_after,
        )


class ModelNotFoundError(OpenRouterError):
    """Raised when the requested model doesn't exist."""

    def __init__(self, model: str):
        super().__init__(f"Model not found: {model}", status_code=404)
        self.model = model


class InvalidRequestError(OpenRouterError):
    """Raised for 4xx client errors (except rate limit)."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message, status_code=status_code)


class ServerError(OpenRouterError):
    """Raised for 5xx server errors."""

    def __init__(self, message: str = "OpenRouter server error", status_code: int = 500):
        super().__init__(message, status_code=status_code)


class OpenRouterConnectionError(OpenRouterError):
    """Raised for network connectivity issues."""

    def __init__(self, message: str = "Failed to connect to OpenRouter"):
        super().__init__(message)


class OpenRouterTimeoutError(OpenRouterError):
    """Raised when request times out."""

    def __init__(self, timeout: float):
        super().__init__(f"Request timed out after {timeout} seconds")
        self.timeout = timeout


class CircuitBreakerOpenError(OpenRouterError):
    """Raised when circuit breaker is open."""

    def __init__(self, model: str, reset_time: float):
        super().__init__(
            f"Circuit breaker open for {model}. Will reset in {reset_time:.1f}s"
        )
        self.model = model
        self.reset_time = reset_time
