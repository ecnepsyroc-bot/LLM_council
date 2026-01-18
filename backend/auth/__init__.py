"""
Authentication package for LLM Council.

Provides API key-based authentication with:
- Secure key generation and hashing
- Permission-based access control
- Audit logging
- Rate limit integration
"""

from .models import (
    Permission,
    APIKeyCreate,
    APIKeyResponse,
    APIKeyCreatedResponse,
    APIKeyInDB,
    AuthenticatedRequest,
)
from .service import APIKeyService
from .middleware import AuthenticationMiddleware
from .dependencies import (
    get_current_auth,
    require_auth,
    require_permission,
    CurrentAuth,
    RequiredAuth,
    AdminAuth,
)
from .exceptions import (
    AuthenticationError,
    InvalidAPIKeyError,
    ExpiredAPIKeyError,
    RevokedAPIKeyError,
    InsufficientPermissionsError,
    RateLimitExceededError,
)

__all__ = [
    # Models
    "Permission",
    "APIKeyCreate",
    "APIKeyResponse",
    "APIKeyCreatedResponse",
    "APIKeyInDB",
    "AuthenticatedRequest",
    # Service
    "APIKeyService",
    # Middleware
    "AuthenticationMiddleware",
    # Dependencies
    "get_current_auth",
    "require_auth",
    "require_permission",
    "CurrentAuth",
    "RequiredAuth",
    "AdminAuth",
    # Exceptions
    "AuthenticationError",
    "InvalidAPIKeyError",
    "ExpiredAPIKeyError",
    "RevokedAPIKeyError",
    "InsufficientPermissionsError",
    "RateLimitExceededError",
]
