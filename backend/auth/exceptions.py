"""Custom exceptions for authentication."""
from fastapi import HTTPException, status


class AuthenticationError(HTTPException):
    """Base class for authentication errors."""

    def __init__(self, detail: str, headers: dict = None):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers=headers or {"WWW-Authenticate": "ApiKey"},
        )


class InvalidAPIKeyError(AuthenticationError):
    """Raised when API key is invalid or malformed."""

    def __init__(self):
        super().__init__("Invalid API key")


class ExpiredAPIKeyError(AuthenticationError):
    """Raised when API key has expired."""

    def __init__(self):
        super().__init__("API key has expired")


class RevokedAPIKeyError(AuthenticationError):
    """Raised when API key has been revoked."""

    def __init__(self):
        super().__init__("API key has been revoked")


class InsufficientPermissionsError(HTTPException):
    """Raised when API key lacks required permissions."""

    def __init__(self, required_permission: str):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"API key lacks required permission: {required_permission}",
        )


class RateLimitExceededError(HTTPException):
    """Raised when API key exceeds its rate limit."""

    def __init__(self, retry_after: int = 60):
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(retry_after)},
        )
