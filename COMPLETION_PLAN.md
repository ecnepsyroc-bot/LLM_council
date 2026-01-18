# LLM Council: Complete Build Plan

**Created:** 2026-01-18
**Status:** Phases 1-3 Complete, Phases 4-9 Pending
**Goal:** 100% Production-Ready with Zero Technical Debt

---

## Current State Assessment

### ✅ Completed (Phases 1-3)

| Phase | Component | Status | Tests |
|-------|-----------|--------|-------|
| 1 | SQLite Storage Migration | Complete | ✓ |
| 2 | Security Hardening (CORS, Rate Limiting, Input Validation) | Complete | ✓ |
| 3 | Testing Infrastructure | Complete | 136 tests |

### ❌ Remaining Work (Phases 4-9)

| Phase | Component | Effort | Priority |
|-------|-----------|--------|----------|
| 4 | Authentication System | 12-16h | CRITICAL |
| 5 | OpenRouter Client Hardening | 8-10h | CRITICAL |
| 6 | Streaming Error Handling | 6-8h | CRITICAL |
| 7 | Model Configuration & Validation | 4-6h | HIGH |
| 8 | Council.py Refactoring | 24-32h | HIGH |
| 9 | Deployment Infrastructure | 16-20h | HIGH |

**Total Estimated Effort:** 70-92 hours

---

## Phase 4: Authentication System

### 4.1 Overview

Implement API key-based authentication with proper security practices. No shortcuts - full implementation with rotation, revocation, and audit logging.

### 4.2 Database Schema

Add to `backend/database/schema.sql`:

```sql
-- API Keys table
CREATE TABLE api_keys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key_hash TEXT NOT NULL UNIQUE,          -- SHA-256 hash of the key
    key_prefix TEXT NOT NULL,               -- First 8 chars for identification (e.g., "llmc_abc1")
    name TEXT NOT NULL,                     -- Human-readable name
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used_at TIMESTAMP,
    expires_at TIMESTAMP,                   -- NULL = never expires
    is_active BOOLEAN DEFAULT TRUE,
    rate_limit_override INTEGER,            -- Custom rate limit (NULL = use default)
    permissions TEXT DEFAULT '["read", "write"]',  -- JSON array of permissions
    metadata TEXT                           -- JSON object for custom data
);

-- API Key usage audit log
CREATE TABLE api_key_audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    api_key_id INTEGER NOT NULL,
    action TEXT NOT NULL,                   -- 'request', 'rate_limited', 'expired', 'revoked'
    endpoint TEXT,
    ip_address TEXT,
    user_agent TEXT,
    request_id TEXT,                        -- UUID for request correlation
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (api_key_id) REFERENCES api_keys(id) ON DELETE CASCADE
);

-- Indexes
CREATE INDEX idx_api_keys_hash ON api_keys(key_hash);
CREATE INDEX idx_api_keys_prefix ON api_keys(key_prefix);
CREATE INDEX idx_api_keys_active ON api_keys(is_active);
CREATE INDEX idx_audit_log_key ON api_key_audit_log(api_key_id);
CREATE INDEX idx_audit_log_created ON api_key_audit_log(created_at);
```

### 4.3 File Structure

```
backend/
├── auth/
│   ├── __init__.py              # Package exports
│   ├── models.py                # Pydantic models for API keys
│   ├── repository.py            # Database operations for API keys
│   ├── service.py               # Business logic (create, validate, revoke)
│   ├── middleware.py            # FastAPI authentication middleware
│   ├── dependencies.py          # FastAPI dependency injection
│   ├── utils.py                 # Key generation, hashing utilities
│   └── exceptions.py            # Custom auth exceptions
```

### 4.4 Implementation: utils.py

```python
"""Authentication utilities for API key management."""
import hashlib
import secrets
import string
from datetime import datetime, timedelta
from typing import Tuple

# Key format: llmc_<32 random chars>
KEY_PREFIX = "llmc_"
KEY_LENGTH = 32
KEY_ALPHABET = string.ascii_letters + string.digits


def generate_api_key() -> Tuple[str, str, str]:
    """
    Generate a new API key.

    Returns:
        Tuple of (full_key, key_prefix, key_hash)
        - full_key: The complete API key to give to the user (shown once)
        - key_prefix: First 8 chars for identification in logs/UI
        - key_hash: SHA-256 hash for secure storage
    """
    random_part = ''.join(secrets.choice(KEY_ALPHABET) for _ in range(KEY_LENGTH))
    full_key = f"{KEY_PREFIX}{random_part}"
    key_prefix = full_key[:12]  # "llmc_" + first 7 random chars
    key_hash = hash_api_key(full_key)

    return full_key, key_prefix, key_hash


def hash_api_key(key: str) -> str:
    """
    Hash an API key for secure storage.

    Uses SHA-256 with a consistent salt derived from the key prefix.
    This allows us to verify keys without storing them in plain text.
    """
    # Use key prefix as salt to prevent rainbow table attacks
    # while still allowing prefix-based lookups
    salt = key[:12] if len(key) >= 12 else key
    salted = f"{salt}:{key}"
    return hashlib.sha256(salted.encode()).hexdigest()


def verify_api_key(provided_key: str, stored_hash: str) -> bool:
    """
    Verify an API key against its stored hash.

    Uses constant-time comparison to prevent timing attacks.
    """
    provided_hash = hash_api_key(provided_key)
    return secrets.compare_digest(provided_hash, stored_hash)


def extract_key_prefix(key: str) -> str:
    """Extract the prefix from an API key for identification."""
    return key[:12] if len(key) >= 12 else key


def is_valid_key_format(key: str) -> bool:
    """Check if a string matches the expected API key format."""
    if not key.startswith(KEY_PREFIX):
        return False
    if len(key) != len(KEY_PREFIX) + KEY_LENGTH:
        return False
    random_part = key[len(KEY_PREFIX):]
    return all(c in KEY_ALPHABET for c in random_part)
```

### 4.5 Implementation: models.py

```python
"""Pydantic models for authentication."""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field
from enum import Enum


class Permission(str, Enum):
    """Available API key permissions."""
    READ = "read"           # Can read conversations
    WRITE = "write"         # Can create/modify conversations
    ADMIN = "admin"         # Can manage API keys
    STREAM = "stream"       # Can use streaming endpoints


class APIKeyCreate(BaseModel):
    """Request model for creating a new API key."""
    name: str = Field(..., min_length=1, max_length=100, description="Human-readable name")
    expires_in_days: Optional[int] = Field(None, ge=1, le=365, description="Days until expiration")
    permissions: List[Permission] = Field(
        default=[Permission.READ, Permission.WRITE, Permission.STREAM],
        description="List of permissions"
    )
    rate_limit_override: Optional[int] = Field(
        None, ge=1, le=10000,
        description="Custom rate limit (requests per minute)"
    )


class APIKeyResponse(BaseModel):
    """Response model for API key operations (excludes sensitive data)."""
    id: int
    key_prefix: str
    name: str
    created_at: datetime
    last_used_at: Optional[datetime]
    expires_at: Optional[datetime]
    is_active: bool
    permissions: List[str]
    rate_limit_override: Optional[int]

    class Config:
        from_attributes = True


class APIKeyCreatedResponse(APIKeyResponse):
    """Response when a new API key is created (includes full key - shown once)."""
    api_key: str = Field(..., description="Full API key - store securely, shown only once")


class APIKeyInDB(BaseModel):
    """Internal model representing API key in database."""
    id: int
    key_hash: str
    key_prefix: str
    name: str
    created_at: datetime
    last_used_at: Optional[datetime]
    expires_at: Optional[datetime]
    is_active: bool
    rate_limit_override: Optional[int]
    permissions: List[str]
    metadata: Optional[dict]


class AuthenticatedRequest(BaseModel):
    """Model representing an authenticated request context."""
    api_key_id: int
    key_prefix: str
    permissions: List[Permission]
    rate_limit: int  # Effective rate limit for this key
    request_id: str  # UUID for request correlation
```

### 4.6 Implementation: exceptions.py

```python
"""Custom exceptions for authentication."""
from fastapi import HTTPException, status


class AuthenticationError(HTTPException):
    """Base class for authentication errors."""
    def __init__(self, detail: str, headers: dict = None):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers=headers or {"WWW-Authenticate": "ApiKey"}
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
            detail=f"API key lacks required permission: {required_permission}"
        )


class RateLimitExceededError(HTTPException):
    """Raised when API key exceeds its rate limit."""
    def __init__(self, retry_after: int = 60):
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(retry_after)}
        )
```

### 4.7 Implementation: repository.py

```python
"""Database operations for API keys."""
import json
from datetime import datetime
from typing import Optional, List
from ..database.connection import get_connection, transaction
from .models import APIKeyInDB
from .utils import hash_api_key, extract_key_prefix


class APIKeyRepository:
    """Repository for API key database operations."""

    def create(
        self,
        key_hash: str,
        key_prefix: str,
        name: str,
        expires_at: Optional[datetime] = None,
        permissions: List[str] = None,
        rate_limit_override: Optional[int] = None
    ) -> APIKeyInDB:
        """Create a new API key record."""
        permissions = permissions or ["read", "write", "stream"]

        with transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO api_keys (key_hash, key_prefix, name, expires_at,
                                      permissions, rate_limit_override)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                key_hash,
                key_prefix,
                name,
                expires_at.isoformat() if expires_at else None,
                json.dumps(permissions),
                rate_limit_override
            ))

            return self.get_by_id(cursor.lastrowid)

    def get_by_id(self, key_id: int) -> Optional[APIKeyInDB]:
        """Get API key by ID."""
        conn = get_connection()
        row = conn.execute(
            "SELECT * FROM api_keys WHERE id = ?", (key_id,)
        ).fetchone()

        return self._row_to_model(row) if row else None

    def get_by_prefix(self, prefix: str) -> Optional[APIKeyInDB]:
        """Get API key by prefix (for verification)."""
        conn = get_connection()
        row = conn.execute(
            "SELECT * FROM api_keys WHERE key_prefix = ?", (prefix,)
        ).fetchone()

        return self._row_to_model(row) if row else None

    def get_by_hash(self, key_hash: str) -> Optional[APIKeyInDB]:
        """Get API key by hash."""
        conn = get_connection()
        row = conn.execute(
            "SELECT * FROM api_keys WHERE key_hash = ?", (key_hash,)
        ).fetchone()

        return self._row_to_model(row) if row else None

    def list_all(self, include_inactive: bool = False) -> List[APIKeyInDB]:
        """List all API keys."""
        conn = get_connection()
        query = "SELECT * FROM api_keys"
        if not include_inactive:
            query += " WHERE is_active = TRUE"
        query += " ORDER BY created_at DESC"

        rows = conn.execute(query).fetchall()
        return [self._row_to_model(row) for row in rows]

    def update_last_used(self, key_id: int) -> None:
        """Update the last_used_at timestamp."""
        conn = get_connection()
        conn.execute(
            "UPDATE api_keys SET last_used_at = ? WHERE id = ?",
            (datetime.utcnow().isoformat(), key_id)
        )

    def revoke(self, key_id: int) -> bool:
        """Revoke an API key."""
        with transaction() as conn:
            cursor = conn.execute(
                "UPDATE api_keys SET is_active = FALSE WHERE id = ?",
                (key_id,)
            )
            return cursor.rowcount > 0

    def delete(self, key_id: int) -> bool:
        """Permanently delete an API key."""
        with transaction() as conn:
            cursor = conn.execute(
                "DELETE FROM api_keys WHERE id = ?", (key_id,)
            )
            return cursor.rowcount > 0

    def log_usage(
        self,
        api_key_id: int,
        action: str,
        endpoint: str = None,
        ip_address: str = None,
        user_agent: str = None,
        request_id: str = None
    ) -> None:
        """Log API key usage for auditing."""
        conn = get_connection()
        conn.execute("""
            INSERT INTO api_key_audit_log
            (api_key_id, action, endpoint, ip_address, user_agent, request_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (api_key_id, action, endpoint, ip_address, user_agent, request_id))

    def _row_to_model(self, row) -> APIKeyInDB:
        """Convert database row to Pydantic model."""
        data = dict(row)
        data['permissions'] = json.loads(data['permissions']) if data['permissions'] else []
        data['metadata'] = json.loads(data['metadata']) if data.get('metadata') else None
        return APIKeyInDB(**data)
```

### 4.8 Implementation: service.py

```python
"""Business logic for API key management."""
import uuid
from datetime import datetime, timedelta
from typing import Optional, List, Tuple

from .models import (
    APIKeyCreate,
    APIKeyResponse,
    APIKeyCreatedResponse,
    APIKeyInDB,
    AuthenticatedRequest,
    Permission
)
from .repository import APIKeyRepository
from .utils import generate_api_key, hash_api_key, verify_api_key, extract_key_prefix, is_valid_key_format
from .exceptions import (
    InvalidAPIKeyError,
    ExpiredAPIKeyError,
    RevokedAPIKeyError,
    InsufficientPermissionsError
)


class APIKeyService:
    """Service for API key operations."""

    def __init__(self, default_rate_limit: int = 60):
        self.repository = APIKeyRepository()
        self.default_rate_limit = default_rate_limit

    def create_key(self, request: APIKeyCreate) -> APIKeyCreatedResponse:
        """
        Create a new API key.

        Returns the full key only once - it cannot be retrieved later.
        """
        # Generate the key
        full_key, key_prefix, key_hash = generate_api_key()

        # Calculate expiration
        expires_at = None
        if request.expires_in_days:
            expires_at = datetime.utcnow() + timedelta(days=request.expires_in_days)

        # Create in database
        db_key = self.repository.create(
            key_hash=key_hash,
            key_prefix=key_prefix,
            name=request.name,
            expires_at=expires_at,
            permissions=[p.value for p in request.permissions],
            rate_limit_override=request.rate_limit_override
        )

        # Return response with full key (shown only once)
        return APIKeyCreatedResponse(
            id=db_key.id,
            api_key=full_key,
            key_prefix=db_key.key_prefix,
            name=db_key.name,
            created_at=db_key.created_at,
            last_used_at=db_key.last_used_at,
            expires_at=db_key.expires_at,
            is_active=db_key.is_active,
            permissions=db_key.permissions,
            rate_limit_override=db_key.rate_limit_override
        )

    def validate_key(
        self,
        api_key: str,
        required_permission: Permission = None,
        endpoint: str = None,
        ip_address: str = None,
        user_agent: str = None
    ) -> AuthenticatedRequest:
        """
        Validate an API key and return authentication context.

        Raises:
            InvalidAPIKeyError: Key is invalid or malformed
            ExpiredAPIKeyError: Key has expired
            RevokedAPIKeyError: Key has been revoked
            InsufficientPermissionsError: Key lacks required permission
        """
        # Check format
        if not api_key or not is_valid_key_format(api_key):
            raise InvalidAPIKeyError()

        # Look up by hash
        key_hash = hash_api_key(api_key)
        db_key = self.repository.get_by_hash(key_hash)

        if not db_key:
            raise InvalidAPIKeyError()

        # Check if revoked
        if not db_key.is_active:
            self.repository.log_usage(db_key.id, "revoked", endpoint, ip_address, user_agent)
            raise RevokedAPIKeyError()

        # Check expiration
        if db_key.expires_at and datetime.utcnow() > db_key.expires_at:
            self.repository.log_usage(db_key.id, "expired", endpoint, ip_address, user_agent)
            raise ExpiredAPIKeyError()

        # Check permission
        if required_permission and required_permission.value not in db_key.permissions:
            self.repository.log_usage(
                db_key.id, "insufficient_permissions", endpoint, ip_address, user_agent
            )
            raise InsufficientPermissionsError(required_permission.value)

        # Generate request ID for correlation
        request_id = str(uuid.uuid4())

        # Log successful authentication
        self.repository.log_usage(db_key.id, "request", endpoint, ip_address, user_agent, request_id)

        # Update last used
        self.repository.update_last_used(db_key.id)

        # Return auth context
        return AuthenticatedRequest(
            api_key_id=db_key.id,
            key_prefix=db_key.key_prefix,
            permissions=[Permission(p) for p in db_key.permissions],
            rate_limit=db_key.rate_limit_override or self.default_rate_limit,
            request_id=request_id
        )

    def list_keys(self, include_inactive: bool = False) -> List[APIKeyResponse]:
        """List all API keys (without sensitive data)."""
        db_keys = self.repository.list_all(include_inactive)
        return [
            APIKeyResponse(
                id=k.id,
                key_prefix=k.key_prefix,
                name=k.name,
                created_at=k.created_at,
                last_used_at=k.last_used_at,
                expires_at=k.expires_at,
                is_active=k.is_active,
                permissions=k.permissions,
                rate_limit_override=k.rate_limit_override
            )
            for k in db_keys
        ]

    def revoke_key(self, key_id: int) -> bool:
        """Revoke an API key."""
        return self.repository.revoke(key_id)

    def delete_key(self, key_id: int) -> bool:
        """Permanently delete an API key."""
        return self.repository.delete(key_id)
```

### 4.9 Implementation: middleware.py

```python
"""FastAPI authentication middleware."""
import os
from typing import Optional
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from .service import APIKeyService
from .models import Permission, AuthenticatedRequest
from .exceptions import AuthenticationError


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """
    Middleware to authenticate requests using API keys.

    Extracts API key from:
    1. X-API-Key header (preferred)
    2. Authorization: Bearer <key> header
    3. api_key query parameter (for WebSocket/SSE compatibility)
    """

    # Endpoints that don't require authentication
    PUBLIC_PATHS = {
        "/",
        "/docs",
        "/redoc",
        "/openapi.json",
    }

    def __init__(self, app, service: APIKeyService = None, bypass_auth: bool = False):
        super().__init__(app)
        self.service = service or APIKeyService()
        self.bypass_auth = bypass_auth or os.getenv("BYPASS_AUTH", "").lower() == "true"

    async def dispatch(self, request: Request, call_next):
        # Skip auth for public paths
        if request.url.path in self.PUBLIC_PATHS:
            return await call_next(request)

        # Skip auth in development/testing if configured
        if self.bypass_auth:
            request.state.auth = None
            return await call_next(request)

        # Extract API key
        api_key = self._extract_api_key(request)

        if not api_key:
            raise HTTPException(
                status_code=401,
                detail="API key required",
                headers={"WWW-Authenticate": "ApiKey"}
            )

        # Determine required permission based on method
        required_permission = self._get_required_permission(request)

        try:
            # Validate and get auth context
            auth_context = self.service.validate_key(
                api_key=api_key,
                required_permission=required_permission,
                endpoint=request.url.path,
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent")
            )

            # Attach auth context to request state
            request.state.auth = auth_context

            # Add request ID to response headers for correlation
            response = await call_next(request)
            response.headers["X-Request-ID"] = auth_context.request_id
            return response

        except AuthenticationError:
            raise
        except Exception as e:
            # Log unexpected errors but don't leak details
            print(f"Authentication error: {e}")
            raise HTTPException(status_code=500, detail="Authentication service error")

    def _extract_api_key(self, request: Request) -> Optional[str]:
        """Extract API key from request."""
        # Try X-API-Key header first
        api_key = request.headers.get("X-API-Key")
        if api_key:
            return api_key

        # Try Authorization header
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            return auth_header[7:]

        # Try query parameter (for SSE/WebSocket)
        api_key = request.query_params.get("api_key")
        if api_key:
            return api_key

        return None

    def _get_required_permission(self, request: Request) -> Permission:
        """Determine required permission based on request."""
        # Streaming endpoints require STREAM permission
        if "/stream" in request.url.path:
            return Permission.STREAM

        # Write operations
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            return Permission.WRITE

        # Read operations
        return Permission.READ
```

### 4.10 Implementation: dependencies.py

```python
"""FastAPI dependency injection for authentication."""
from typing import Annotated, Optional
from fastapi import Depends, Request, HTTPException

from .models import AuthenticatedRequest, Permission
from .exceptions import InsufficientPermissionsError


def get_current_auth(request: Request) -> Optional[AuthenticatedRequest]:
    """
    Dependency to get current authentication context.

    Returns None if auth is bypassed (development mode).
    Raises 401 if no auth context and auth is required.
    """
    auth = getattr(request.state, 'auth', None)
    return auth


def require_auth(request: Request) -> AuthenticatedRequest:
    """
    Dependency that requires authentication.

    Raises 401 if not authenticated.
    """
    auth = get_current_auth(request)
    if auth is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return auth


def require_permission(permission: Permission):
    """
    Factory for permission-checking dependencies.

    Usage:
        @app.get("/admin/keys")
        def list_keys(auth: AuthenticatedRequest = Depends(require_permission(Permission.ADMIN))):
            ...
    """
    def dependency(auth: AuthenticatedRequest = Depends(require_auth)) -> AuthenticatedRequest:
        if permission not in auth.permissions:
            raise InsufficientPermissionsError(permission.value)
        return auth
    return dependency


# Convenience type aliases
CurrentAuth = Annotated[Optional[AuthenticatedRequest], Depends(get_current_auth)]
RequiredAuth = Annotated[AuthenticatedRequest, Depends(require_auth)]
AdminAuth = Annotated[AuthenticatedRequest, Depends(require_permission(Permission.ADMIN))]
```

### 4.11 API Key Management Endpoints

Add to `backend/main.py`:

```python
from .auth import (
    APIKeyService,
    APIKeyCreate,
    APIKeyResponse,
    APIKeyCreatedResponse,
    AuthenticationMiddleware,
    require_auth,
    require_permission,
    Permission,
    RequiredAuth,
    AdminAuth
)

# Initialize auth service
auth_service = APIKeyService(default_rate_limit=60)

# Add authentication middleware (after rate limiting)
app.add_middleware(
    AuthenticationMiddleware,
    service=auth_service,
    bypass_auth=os.getenv("TESTING", "").lower() == "true"
)


# API Key Management Endpoints
@app.post("/api/keys", response_model=APIKeyCreatedResponse, tags=["Authentication"])
async def create_api_key(
    request: APIKeyCreate,
    auth: AdminAuth  # Requires admin permission
):
    """
    Create a new API key.

    **Important:** The full API key is only shown once in this response.
    Store it securely - it cannot be retrieved later.

    Requires admin permission.
    """
    return auth_service.create_key(request)


@app.get("/api/keys", response_model=list[APIKeyResponse], tags=["Authentication"])
async def list_api_keys(
    include_inactive: bool = False,
    auth: AdminAuth
):
    """
    List all API keys (without sensitive data).

    Requires admin permission.
    """
    return auth_service.list_keys(include_inactive)


@app.delete("/api/keys/{key_id}", tags=["Authentication"])
async def revoke_api_key(
    key_id: int,
    auth: AdminAuth
):
    """
    Revoke an API key.

    The key will no longer be valid for authentication.
    Requires admin permission.
    """
    if auth_service.revoke_key(key_id):
        return {"status": "revoked", "key_id": key_id}
    raise HTTPException(status_code=404, detail="API key not found")


@app.get("/api/auth/me", tags=["Authentication"])
async def get_current_user(auth: RequiredAuth):
    """
    Get information about the current API key.

    Useful for verifying authentication is working.
    """
    return {
        "key_prefix": auth.key_prefix,
        "permissions": [p.value for p in auth.permissions],
        "rate_limit": auth.rate_limit,
        "request_id": auth.request_id
    }
```

### 4.12 Bootstrap Script for Initial API Key

Create `backend/auth/bootstrap.py`:

```python
"""Bootstrap script to create initial admin API key."""
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.database.connection import init_database
from backend.auth.service import APIKeyService
from backend.auth.models import APIKeyCreate, Permission


def bootstrap_admin_key():
    """Create an initial admin API key for bootstrapping."""
    print("=" * 60)
    print("LLM Council - API Key Bootstrap")
    print("=" * 60)

    # Initialize database (ensures tables exist)
    init_database()

    # Create admin key
    service = APIKeyService()

    request = APIKeyCreate(
        name="Bootstrap Admin Key",
        permissions=[Permission.READ, Permission.WRITE, Permission.ADMIN, Permission.STREAM],
        expires_in_days=None  # Never expires
    )

    result = service.create_key(request)

    print("\n✅ Admin API key created successfully!\n")
    print("-" * 60)
    print(f"API Key: {result.api_key}")
    print("-" * 60)
    print("\n⚠️  IMPORTANT: Save this key securely!")
    print("   This is the ONLY time it will be displayed.\n")
    print("Usage:")
    print(f'  curl -H "X-API-Key: {result.api_key}" http://localhost:8001/api/auth/me')
    print("\nOr set environment variable:")
    print(f'  export LLM_COUNCIL_API_KEY="{result.api_key}"')
    print("=" * 60)


if __name__ == "__main__":
    bootstrap_admin_key()
```

### 4.13 Tests for Authentication

Create `backend/tests/test_auth.py`:

```python
"""Tests for authentication system."""
import pytest
from datetime import datetime, timedelta

from backend.auth.utils import (
    generate_api_key,
    hash_api_key,
    verify_api_key,
    is_valid_key_format,
    extract_key_prefix
)
from backend.auth.models import APIKeyCreate, Permission
from backend.auth.service import APIKeyService
from backend.auth.exceptions import (
    InvalidAPIKeyError,
    ExpiredAPIKeyError,
    RevokedAPIKeyError,
    InsufficientPermissionsError
)


class TestAPIKeyUtils:
    """Tests for API key utility functions."""

    def test_generate_api_key_format(self):
        """Generated keys have correct format."""
        full_key, prefix, key_hash = generate_api_key()

        assert full_key.startswith("llmc_")
        assert len(full_key) == 37  # "llmc_" + 32 chars
        assert prefix == full_key[:12]
        assert len(key_hash) == 64  # SHA-256 hex

    def test_generate_api_key_uniqueness(self):
        """Each generated key is unique."""
        keys = [generate_api_key()[0] for _ in range(100)]
        assert len(set(keys)) == 100

    def test_hash_api_key_deterministic(self):
        """Same key produces same hash."""
        key = "llmc_abcdefghijklmnopqrstuvwxyz1234"
        hash1 = hash_api_key(key)
        hash2 = hash_api_key(key)
        assert hash1 == hash2

    def test_hash_api_key_different_keys(self):
        """Different keys produce different hashes."""
        key1 = "llmc_abcdefghijklmnopqrstuvwxyz1234"
        key2 = "llmc_abcdefghijklmnopqrstuvwxyz1235"
        assert hash_api_key(key1) != hash_api_key(key2)

    def test_verify_api_key_valid(self):
        """Valid key verifies correctly."""
        full_key, _, key_hash = generate_api_key()
        assert verify_api_key(full_key, key_hash)

    def test_verify_api_key_invalid(self):
        """Invalid key fails verification."""
        full_key, _, key_hash = generate_api_key()
        wrong_key = full_key[:-1] + "X"
        assert not verify_api_key(wrong_key, key_hash)

    def test_is_valid_key_format_valid(self):
        """Valid format passes."""
        assert is_valid_key_format("llmc_abcdefghijklmnopqrstuvwxyz12")

    def test_is_valid_key_format_wrong_prefix(self):
        """Wrong prefix fails."""
        assert not is_valid_key_format("xxxx_abcdefghijklmnopqrstuvwxyz12")

    def test_is_valid_key_format_wrong_length(self):
        """Wrong length fails."""
        assert not is_valid_key_format("llmc_abc")

    def test_is_valid_key_format_invalid_chars(self):
        """Invalid characters fail."""
        assert not is_valid_key_format("llmc_abc!@#$%^&*()_+{}|:<>?1234567")


class TestAPIKeyService:
    """Tests for API key service."""

    @pytest.fixture
    def service(self, temp_db):
        """Get service with test database."""
        return APIKeyService(default_rate_limit=60)

    def test_create_key(self, service):
        """Create a new API key."""
        request = APIKeyCreate(
            name="Test Key",
            permissions=[Permission.READ, Permission.WRITE]
        )

        result = service.create_key(request)

        assert result.name == "Test Key"
        assert result.api_key.startswith("llmc_")
        assert result.is_active
        assert "read" in result.permissions
        assert "write" in result.permissions

    def test_create_key_with_expiration(self, service):
        """Create key with expiration."""
        request = APIKeyCreate(
            name="Expiring Key",
            expires_in_days=30
        )

        result = service.create_key(request)

        assert result.expires_at is not None
        assert result.expires_at > datetime.utcnow()

    def test_validate_key_success(self, service):
        """Validate a valid key."""
        request = APIKeyCreate(name="Valid Key")
        created = service.create_key(request)

        auth = service.validate_key(created.api_key)

        assert auth.key_prefix == created.key_prefix
        assert Permission.READ in auth.permissions

    def test_validate_key_invalid(self, service):
        """Invalid key raises error."""
        with pytest.raises(InvalidAPIKeyError):
            service.validate_key("llmc_invalid_key_that_does_not_exist")

    def test_validate_key_revoked(self, service):
        """Revoked key raises error."""
        request = APIKeyCreate(name="Revoked Key")
        created = service.create_key(request)

        service.revoke_key(created.id)

        with pytest.raises(RevokedAPIKeyError):
            service.validate_key(created.api_key)

    def test_validate_key_permission_check(self, service):
        """Permission check works."""
        request = APIKeyCreate(
            name="Read Only Key",
            permissions=[Permission.READ]  # No write permission
        )
        created = service.create_key(request)

        # Read should work
        auth = service.validate_key(created.api_key, Permission.READ)
        assert auth is not None

        # Write should fail
        with pytest.raises(InsufficientPermissionsError):
            service.validate_key(created.api_key, Permission.WRITE)

    def test_list_keys(self, service):
        """List all keys."""
        # Create a few keys
        for i in range(3):
            service.create_key(APIKeyCreate(name=f"Key {i}"))

        keys = service.list_keys()

        assert len(keys) >= 3
        # Keys should not include the actual key value
        for key in keys:
            assert not hasattr(key, 'api_key') or key.api_key is None

    def test_revoke_key(self, service):
        """Revoke a key."""
        created = service.create_key(APIKeyCreate(name="To Revoke"))

        result = service.revoke_key(created.id)

        assert result is True

        # Key should no longer validate
        with pytest.raises(RevokedAPIKeyError):
            service.validate_key(created.api_key)


class TestAuthenticationMiddleware:
    """Tests for authentication middleware."""

    def test_public_paths_no_auth(self, test_client):
        """Public paths don't require auth."""
        response = test_client.get("/")
        assert response.status_code == 200

    def test_protected_path_requires_auth(self, test_client_with_auth):
        """Protected paths require auth."""
        response = test_client_with_auth.get("/api/conversations")
        assert response.status_code == 401

    def test_protected_path_with_valid_key(self, test_client_with_auth, api_key):
        """Valid key allows access."""
        response = test_client_with_auth.get(
            "/api/conversations",
            headers={"X-API-Key": api_key}
        )
        assert response.status_code == 200

    def test_request_id_in_response(self, test_client_with_auth, api_key):
        """Request ID is included in response."""
        response = test_client_with_auth.get(
            "/api/conversations",
            headers={"X-API-Key": api_key}
        )
        assert "X-Request-ID" in response.headers
```

### 4.14 Documentation

Create `docs/AUTHENTICATION.md`:

```markdown
# LLM Council Authentication

## Overview

LLM Council uses API key authentication to secure access to the API. API keys are:

- **Secure**: Keys are hashed using SHA-256 before storage
- **Auditable**: All API key usage is logged
- **Flexible**: Keys can have custom permissions and rate limits
- **Expirable**: Keys can be set to expire after a certain period

## Quick Start

### 1. Generate Initial Admin Key

```bash
# Run the bootstrap script to create your first admin key
uv run python -m backend.auth.bootstrap
```

This will output an API key that looks like:
```
llmc_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6
```

**⚠️ Save this key securely! It will only be shown once.**

### 2. Use the API Key

Include the key in your requests using one of these methods:

**Header (Recommended):**
```bash
curl -H "X-API-Key: llmc_your_key_here" http://localhost:8001/api/conversations
```

**Bearer Token:**
```bash
curl -H "Authorization: Bearer llmc_your_key_here" http://localhost:8001/api/conversations
```

**Query Parameter (for SSE/WebSocket):**
```bash
curl "http://localhost:8001/api/conversations?api_key=llmc_your_key_here"
```

### 3. Verify Authentication

```bash
curl -H "X-API-Key: llmc_your_key_here" http://localhost:8001/api/auth/me
```

Response:
```json
{
  "key_prefix": "llmc_a1b2c3d4",
  "permissions": ["read", "write", "stream"],
  "rate_limit": 60,
  "request_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

## API Key Permissions

| Permission | Description | Required For |
|------------|-------------|--------------|
| `read` | Read conversations | GET endpoints |
| `write` | Create/modify data | POST, PATCH, DELETE endpoints |
| `stream` | Use streaming | `/stream` endpoints |
| `admin` | Manage API keys | `/api/keys` endpoints |

## Managing API Keys

### Create a New Key (Requires Admin)

```bash
curl -X POST \
  -H "X-API-Key: llmc_admin_key" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My App Key",
    "permissions": ["read", "write", "stream"],
    "expires_in_days": 90
  }' \
  http://localhost:8001/api/keys
```

### List All Keys (Requires Admin)

```bash
curl -H "X-API-Key: llmc_admin_key" http://localhost:8001/api/keys
```

### Revoke a Key (Requires Admin)

```bash
curl -X DELETE \
  -H "X-API-Key: llmc_admin_key" \
  http://localhost:8001/api/keys/123
```

## Security Best Practices

1. **Never commit API keys** to version control
2. **Use environment variables** to store keys:
   ```bash
   export LLM_COUNCIL_API_KEY="llmc_your_key"
   ```
3. **Rotate keys regularly** - Create new keys and revoke old ones
4. **Use minimal permissions** - Only grant permissions that are needed
5. **Set expiration dates** - Use `expires_in_days` for temporary access
6. **Monitor usage** - Check the audit log for suspicious activity

## Rate Limiting

Each API key has a rate limit (default: 60 requests/minute). You can set custom limits:

```json
{
  "name": "High Volume Key",
  "rate_limit_override": 300
}
```

Rate limit headers are included in responses:
- `X-RateLimit-Limit`: Maximum requests per minute
- `X-RateLimit-Remaining`: Requests remaining in current window

## Audit Logging

All API key usage is logged with:
- Timestamp
- Endpoint accessed
- IP address
- User agent
- Request ID (for correlation)
- Action (request, rate_limited, expired, revoked)

Query the audit log directly in SQLite if needed:
```sql
SELECT * FROM api_key_audit_log
WHERE api_key_id = ?
ORDER BY created_at DESC
LIMIT 100;
```

## Development Mode

To bypass authentication during development:

```bash
export BYPASS_AUTH=true
uv run python -m backend.main
```

**⚠️ Never use this in production!**

## Troubleshooting

### "API key required" (401)
- Ensure you're including the key in the request
- Check the header name is exactly `X-API-Key`

### "Invalid API key" (401)
- Verify the key is correct and complete
- Keys start with `llmc_` and are 37 characters total

### "API key has expired" (401)
- Create a new key with a longer expiration
- Or create a key without expiration (`expires_in_days: null`)

### "API key has been revoked" (401)
- The key was intentionally disabled
- Create a new key if access is still needed

### "Insufficient permissions" (403)
- Your key doesn't have the required permission
- Create a new key with the needed permissions
```

---

## Phase 5: OpenRouter Client Hardening

### 5.1 Overview

Replace the current simple HTTP client with a robust client that includes:
- Retry logic with exponential backoff
- Rate limit detection and respect
- Circuit breaker pattern
- Proper logging
- Configurable timeouts
- Error classification

### 5.2 File Structure

```
backend/
├── openrouter/
│   ├── __init__.py              # Package exports
│   ├── client.py                # Main HTTP client
│   ├── retry.py                 # Retry decorator with backoff
│   ├── circuit_breaker.py       # Circuit breaker implementation
│   ├── exceptions.py            # Custom exceptions
│   ├── models.py                # Request/response models
│   └── config.py                # Client configuration
```

### 5.3 Implementation: exceptions.py

```python
"""Custom exceptions for OpenRouter client."""
from typing import Optional


class OpenRouterError(Exception):
    """Base exception for OpenRouter errors."""
    def __init__(self, message: str, status_code: Optional[int] = None, retry_after: Optional[int] = None):
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
            retry_after=retry_after
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


class ConnectionError(OpenRouterError):
    """Raised for network connectivity issues."""
    def __init__(self, message: str = "Failed to connect to OpenRouter"):
        super().__init__(message)


class TimeoutError(OpenRouterError):
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
```

### 5.4 Implementation: config.py

```python
"""Configuration for OpenRouter client."""
from dataclasses import dataclass, field
from typing import Optional
import os


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_retries: int = 3
    initial_delay: float = 1.0          # Initial delay in seconds
    max_delay: float = 60.0             # Maximum delay in seconds
    exponential_base: float = 2.0       # Exponential backoff base
    jitter: bool = True                 # Add random jitter to delays

    # Which status codes to retry
    retryable_status_codes: tuple = (408, 429, 500, 502, 503, 504)


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""
    failure_threshold: int = 5          # Failures before opening circuit
    success_threshold: int = 2          # Successes before closing circuit
    timeout: float = 60.0               # Time to wait before half-open state

    # Track per-model or global
    per_model: bool = True


@dataclass
class TimeoutConfig:
    """Configuration for request timeouts."""
    connect_timeout: float = 10.0       # Time to establish connection
    read_timeout: float = 120.0         # Time to receive response

    # Per-model timeout overrides
    model_timeouts: dict = field(default_factory=dict)

    def get_timeout(self, model: str) -> tuple[float, float]:
        """Get timeout for a specific model."""
        if model in self.model_timeouts:
            return self.model_timeouts[model]
        return (self.connect_timeout, self.read_timeout)


@dataclass
class OpenRouterConfig:
    """Complete configuration for OpenRouter client."""
    api_key: str = field(default_factory=lambda: os.getenv("OPENROUTER_API_KEY", ""))
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
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY environment variable is required")
```

### 5.5 Implementation: retry.py

```python
"""Retry decorator with exponential backoff."""
import asyncio
import random
import functools
import logging
from typing import Callable, Type, Tuple, Optional

from .config import RetryConfig
from .exceptions import OpenRouterError, RateLimitError, ServerError

logger = logging.getLogger(__name__)


def calculate_delay(
    attempt: int,
    config: RetryConfig,
    retry_after: Optional[int] = None
) -> float:
    """Calculate delay before next retry attempt."""
    if retry_after:
        # Respect Retry-After header
        return min(retry_after, config.max_delay)

    # Exponential backoff
    delay = config.initial_delay * (config.exponential_base ** attempt)
    delay = min(delay, config.max_delay)

    # Add jitter to prevent thundering herd
    if config.jitter:
        delay = delay * (0.5 + random.random())

    return delay


def with_retry(
    config: RetryConfig = None,
    retryable_exceptions: Tuple[Type[Exception], ...] = (ServerError, RateLimitError)
):
    """
    Decorator for retrying async functions with exponential backoff.

    Usage:
        @with_retry(RetryConfig(max_retries=3))
        async def my_function():
            ...
    """
    config = config or RetryConfig()

    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(config.max_retries + 1):
                try:
                    return await func(*args, **kwargs)

                except retryable_exceptions as e:
                    last_exception = e

                    if attempt == config.max_retries:
                        logger.error(
                            f"Max retries ({config.max_retries}) exceeded for {func.__name__}: {e}"
                        )
                        raise

                    # Get retry_after if available (for rate limits)
                    retry_after = getattr(e, 'retry_after', None)
                    delay = calculate_delay(attempt, config, retry_after)

                    logger.warning(
                        f"Retry {attempt + 1}/{config.max_retries} for {func.__name__} "
                        f"after {delay:.1f}s: {e}"
                    )

                    await asyncio.sleep(delay)

                except Exception as e:
                    # Non-retryable exception
                    logger.error(f"Non-retryable error in {func.__name__}: {e}")
                    raise

            # Should not reach here, but just in case
            raise last_exception

        return wrapper
    return decorator


class RetryableOperation:
    """
    Context manager for retryable operations with progress tracking.

    Usage:
        async with RetryableOperation(config, "query_model") as op:
            result = await op.execute(my_async_func, *args, **kwargs)
    """

    def __init__(self, config: RetryConfig, operation_name: str):
        self.config = config
        self.operation_name = operation_name
        self.attempts = 0
        self.last_error = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    async def execute(self, func: Callable, *args, **kwargs):
        """Execute function with retry logic."""
        for attempt in range(self.config.max_retries + 1):
            self.attempts = attempt + 1

            try:
                return await func(*args, **kwargs)

            except (ServerError, RateLimitError) as e:
                self.last_error = e

                if attempt == self.config.max_retries:
                    raise

                retry_after = getattr(e, 'retry_after', None)
                delay = calculate_delay(attempt, self.config, retry_after)

                logger.warning(
                    f"{self.operation_name}: Retry {attempt + 1}/{self.config.max_retries} "
                    f"after {delay:.1f}s"
                )

                await asyncio.sleep(delay)
```

### 5.6 Implementation: circuit_breaker.py

```python
"""Circuit breaker pattern implementation."""
import asyncio
import time
import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, Optional

from .config import CircuitBreakerConfig
from .exceptions import CircuitBreakerOpenError

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if recovered


@dataclass
class CircuitStats:
    """Statistics for a single circuit."""
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: Optional[float] = None
    last_state_change: float = field(default_factory=time.time)


class CircuitBreaker:
    """
    Circuit breaker to prevent cascading failures.

    When a service fails repeatedly, the circuit "opens" and
    subsequent requests fail fast without actually calling the service.
    After a timeout, the circuit moves to "half-open" state and
    allows a test request through.
    """

    def __init__(self, config: CircuitBreakerConfig = None):
        self.config = config or CircuitBreakerConfig()
        self._circuits: Dict[str, CircuitStats] = {}
        self._lock = asyncio.Lock()

    def _get_circuit(self, key: str) -> CircuitStats:
        """Get or create circuit for a key."""
        if key not in self._circuits:
            self._circuits[key] = CircuitStats()
        return self._circuits[key]

    async def can_execute(self, key: str) -> bool:
        """
        Check if a request can proceed.

        Returns True if allowed, raises CircuitBreakerOpenError if not.
        """
        async with self._lock:
            circuit = self._get_circuit(key)

            if circuit.state == CircuitState.CLOSED:
                return True

            if circuit.state == CircuitState.OPEN:
                # Check if timeout has passed
                time_since_open = time.time() - circuit.last_state_change

                if time_since_open >= self.config.timeout:
                    # Move to half-open
                    circuit.state = CircuitState.HALF_OPEN
                    circuit.last_state_change = time.time()
                    circuit.success_count = 0
                    logger.info(f"Circuit {key}: OPEN -> HALF_OPEN")
                    return True
                else:
                    # Still open
                    remaining = self.config.timeout - time_since_open
                    raise CircuitBreakerOpenError(key, remaining)

            # Half-open: allow one request through
            return True

    async def record_success(self, key: str) -> None:
        """Record a successful request."""
        async with self._lock:
            circuit = self._get_circuit(key)

            if circuit.state == CircuitState.HALF_OPEN:
                circuit.success_count += 1

                if circuit.success_count >= self.config.success_threshold:
                    # Recovery confirmed, close circuit
                    circuit.state = CircuitState.CLOSED
                    circuit.failure_count = 0
                    circuit.success_count = 0
                    circuit.last_state_change = time.time()
                    logger.info(f"Circuit {key}: HALF_OPEN -> CLOSED (recovered)")

            elif circuit.state == CircuitState.CLOSED:
                # Reset failure count on success
                circuit.failure_count = 0

    async def record_failure(self, key: str) -> None:
        """Record a failed request."""
        async with self._lock:
            circuit = self._get_circuit(key)
            circuit.failure_count += 1
            circuit.last_failure_time = time.time()

            if circuit.state == CircuitState.HALF_OPEN:
                # Failed during test, back to open
                circuit.state = CircuitState.OPEN
                circuit.last_state_change = time.time()
                logger.warning(f"Circuit {key}: HALF_OPEN -> OPEN (test failed)")

            elif circuit.state == CircuitState.CLOSED:
                if circuit.failure_count >= self.config.failure_threshold:
                    # Too many failures, open circuit
                    circuit.state = CircuitState.OPEN
                    circuit.last_state_change = time.time()
                    logger.warning(
                        f"Circuit {key}: CLOSED -> OPEN "
                        f"({circuit.failure_count} failures)"
                    )

    def get_stats(self, key: str) -> Optional[CircuitStats]:
        """Get statistics for a circuit."""
        return self._circuits.get(key)

    def get_all_stats(self) -> Dict[str, CircuitStats]:
        """Get statistics for all circuits."""
        return dict(self._circuits)

    async def reset(self, key: str) -> None:
        """Manually reset a circuit to closed state."""
        async with self._lock:
            if key in self._circuits:
                self._circuits[key] = CircuitStats()
                logger.info(f"Circuit {key}: manually reset to CLOSED")
```

### 5.7 Implementation: client.py

```python
"""Robust OpenRouter HTTP client."""
import asyncio
import json
import logging
import httpx
from typing import Optional, Dict, Any, AsyncGenerator, List

from .config import OpenRouterConfig, RetryConfig
from .retry import with_retry, RetryableOperation
from .circuit_breaker import CircuitBreaker
from .exceptions import (
    OpenRouterError,
    RateLimitError,
    ModelNotFoundError,
    InvalidRequestError,
    ServerError,
    ConnectionError,
    TimeoutError,
    CircuitBreakerOpenError
)

logger = logging.getLogger(__name__)


class OpenRouterClient:
    """
    Robust HTTP client for OpenRouter API.

    Features:
    - Retry with exponential backoff
    - Circuit breaker per model
    - Rate limit detection and respect
    - Configurable timeouts
    - Comprehensive error handling
    - Request/response logging
    """

    def __init__(self, config: OpenRouterConfig = None):
        self.config = config or OpenRouterConfig()
        self.circuit_breaker = CircuitBreaker(self.config.circuit_breaker)

        # HTTP client will be created per-request for proper async handling
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.config.base_url,
                headers={
                    "Authorization": f"Bearer {self.config.api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://llm-council.local",
                    "X-Title": "LLM Council"
                }
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    def _handle_response_error(self, response: httpx.Response, model: str) -> None:
        """Convert HTTP errors to appropriate exceptions."""
        status = response.status_code

        try:
            error_data = response.json()
            message = error_data.get("error", {}).get("message", response.text)
        except:
            message = response.text

        if status == 429:
            # Rate limit - extract Retry-After if available
            retry_after = int(response.headers.get("Retry-After", 60))
            raise RateLimitError(retry_after)

        elif status == 404:
            raise ModelNotFoundError(model)

        elif status == 400:
            raise InvalidRequestError(message, status)

        elif status == 401:
            raise InvalidRequestError("Invalid API key", 401)

        elif status == 403:
            raise InvalidRequestError("Access forbidden", 403)

        elif status >= 500:
            raise ServerError(message, status)

        elif status >= 400:
            raise InvalidRequestError(message, status)

    async def query(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = None,
        max_tokens: int = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Send a query to a model and get a response.

        Args:
            model: Model identifier (e.g., "openai/gpt-4")
            messages: List of message dicts with "role" and "content"
            temperature: Sampling temperature (0-2)
            max_tokens: Maximum tokens in response
            **kwargs: Additional parameters to pass to the API

        Returns:
            Dict with "content" and optional "reasoning_details"

        Raises:
            OpenRouterError subclass on failure
        """
        # Check circuit breaker
        circuit_key = model if self.config.circuit_breaker.per_model else "global"
        await self.circuit_breaker.can_execute(circuit_key)

        # Build request
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature or self.config.default_temperature,
            "max_tokens": max_tokens or self.config.default_max_tokens,
            **kwargs
        }

        connect_timeout, read_timeout = self.config.timeout.get_timeout(model)

        if self.config.log_requests:
            logger.info(f"OpenRouter request: model={model}, messages={len(messages)}")

        try:
            client = await self._get_client()

            response = await client.post(
                "/chat/completions",
                json=payload,
                timeout=httpx.Timeout(connect_timeout, read=read_timeout)
            )

            if response.status_code != 200:
                self._handle_response_error(response, model)

            data = response.json()

            # Record success
            await self.circuit_breaker.record_success(circuit_key)

            # Extract response
            result = {
                "content": data["choices"][0]["message"]["content"]
            }

            # Check for reasoning details (o1, etc.)
            if "reasoning_content" in data["choices"][0]["message"]:
                result["reasoning_details"] = data["choices"][0]["message"]["reasoning_content"]

            if self.config.log_responses:
                logger.info(f"OpenRouter response: model={model}, length={len(result['content'])}")

            return result

        except httpx.TimeoutException:
            await self.circuit_breaker.record_failure(circuit_key)
            raise TimeoutError(read_timeout)

        except httpx.ConnectError as e:
            await self.circuit_breaker.record_failure(circuit_key)
            raise ConnectionError(str(e))

        except (RateLimitError, ServerError) as e:
            await self.circuit_breaker.record_failure(circuit_key)
            raise

        except OpenRouterError:
            # Don't record client errors as circuit failures
            raise

        except Exception as e:
            await self.circuit_breaker.record_failure(circuit_key)
            logger.exception(f"Unexpected error querying {model}")
            raise OpenRouterError(f"Unexpected error: {e}")

    async def query_with_retry(
        self,
        model: str,
        messages: List[Dict[str, str]],
        retry_config: RetryConfig = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Query with automatic retry on transient failures.

        Uses exponential backoff with jitter.
        """
        config = retry_config or self.config.retry

        async with RetryableOperation(config, f"query_{model}") as op:
            return await op.execute(
                self.query,
                model=model,
                messages=messages,
                **kwargs
            )

    async def stream(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = None,
        max_tokens: int = None,
        **kwargs
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream a response from a model.

        Yields events with:
        - type: "content" | "done" | "error"
        - content: Partial content (for "content" type)
        - full_content: Complete content (for "done" type)
        """
        circuit_key = model if self.config.circuit_breaker.per_model else "global"
        await self.circuit_breaker.can_execute(circuit_key)

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature or self.config.default_temperature,
            "max_tokens": max_tokens or self.config.default_max_tokens,
            "stream": True,
            **kwargs
        }

        connect_timeout, read_timeout = self.config.timeout.get_timeout(model)
        full_content = ""

        try:
            client = await self._get_client()

            async with client.stream(
                "POST",
                "/chat/completions",
                json=payload,
                timeout=httpx.Timeout(connect_timeout, read=read_timeout)
            ) as response:

                if response.status_code != 200:
                    # Read full response for error details
                    await response.aread()
                    self._handle_response_error(response, model)

                async for line in response.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue

                    data = line[6:]  # Remove "data: " prefix

                    if data == "[DONE]":
                        break

                    try:
                        chunk = json.loads(data)
                        delta = chunk["choices"][0]["delta"]

                        if "content" in delta:
                            content = delta["content"]
                            full_content += content
                            yield {
                                "type": "content",
                                "content": content,
                                "full_content": full_content
                            }

                    except json.JSONDecodeError:
                        continue

            # Record success
            await self.circuit_breaker.record_success(circuit_key)

            yield {
                "type": "done",
                "full_content": full_content
            }

        except httpx.TimeoutException:
            await self.circuit_breaker.record_failure(circuit_key)
            yield {"type": "error", "error": f"Timeout after {read_timeout}s"}

        except httpx.ConnectError as e:
            await self.circuit_breaker.record_failure(circuit_key)
            yield {"type": "error", "error": f"Connection failed: {e}"}

        except OpenRouterError as e:
            if isinstance(e, (RateLimitError, ServerError)):
                await self.circuit_breaker.record_failure(circuit_key)
            yield {"type": "error", "error": str(e)}

        except Exception as e:
            await self.circuit_breaker.record_failure(circuit_key)
            logger.exception(f"Unexpected error streaming {model}")
            yield {"type": "error", "error": f"Unexpected error: {e}"}

    async def validate_model(self, model: str) -> bool:
        """
        Check if a model is available and accessible.

        Returns True if valid, False otherwise.
        """
        try:
            # Send minimal request to test model
            await self.query(
                model=model,
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=1
            )
            return True
        except ModelNotFoundError:
            return False
        except InvalidRequestError:
            # Model exists but request was invalid (still accessible)
            return True
        except Exception:
            return False

    def get_circuit_stats(self) -> Dict[str, Any]:
        """Get circuit breaker statistics for monitoring."""
        stats = self.circuit_breaker.get_all_stats()
        return {
            key: {
                "state": stat.state.value,
                "failure_count": stat.failure_count,
                "success_count": stat.success_count,
                "last_failure": stat.last_failure_time
            }
            for key, stat in stats.items()
        }
```

### 5.8 Package Export

Create `backend/openrouter/__init__.py`:

```python
"""
OpenRouter client package.

Provides a robust HTTP client for the OpenRouter API with:
- Retry with exponential backoff
- Circuit breaker pattern
- Rate limit handling
- Comprehensive error classification
"""

from .client import OpenRouterClient
from .config import OpenRouterConfig, RetryConfig, CircuitBreakerConfig, TimeoutConfig
from .exceptions import (
    OpenRouterError,
    RateLimitError,
    ModelNotFoundError,
    InvalidRequestError,
    ServerError,
    ConnectionError,
    TimeoutError,
    CircuitBreakerOpenError
)

__all__ = [
    "OpenRouterClient",
    "OpenRouterConfig",
    "RetryConfig",
    "CircuitBreakerConfig",
    "TimeoutConfig",
    "OpenRouterError",
    "RateLimitError",
    "ModelNotFoundError",
    "InvalidRequestError",
    "ServerError",
    "ConnectionError",
    "TimeoutError",
    "CircuitBreakerOpenError",
]
```

---

## Phase 6: Streaming Error Handling

### 6.1 Overview

Implement proper error handling for the streaming endpoint with:
- Per-stage error context
- Model-level error tracking
- Graceful partial recovery
- Detailed error events
- Timeout handling

### 6.2 Implementation: Streaming Event Types

Create `backend/streaming/events.py`:

```python
"""Event types for streaming responses."""
from dataclasses import dataclass, asdict
from typing import Optional, Any, Dict, List
from enum import Enum
import json


class EventType(str, Enum):
    """Types of streaming events."""
    # Stage lifecycle
    STAGE_START = "stage_start"
    STAGE_COMPLETE = "stage_complete"
    STAGE_ERROR = "stage_error"

    # Model events
    MODEL_START = "model_start"
    MODEL_CHUNK = "model_chunk"
    MODEL_COMPLETE = "model_complete"
    MODEL_ERROR = "model_error"

    # Overall
    DELIBERATION_START = "deliberation_start"
    DELIBERATION_COMPLETE = "deliberation_complete"
    DELIBERATION_ERROR = "deliberation_error"

    # Progress
    PROGRESS = "progress"


@dataclass
class StreamEvent:
    """Base class for streaming events."""
    type: EventType

    def to_sse(self) -> str:
        """Convert to Server-Sent Event format."""
        data = asdict(self)
        data["type"] = self.type.value
        return f"data: {json.dumps(data)}\n\n"


@dataclass
class StageStartEvent(StreamEvent):
    """Emitted when a stage begins."""
    type: EventType = EventType.STAGE_START
    stage: int = 0
    stage_name: str = ""
    models: List[str] = None

    def __post_init__(self):
        self.models = self.models or []


@dataclass
class StageCompleteEvent(StreamEvent):
    """Emitted when a stage completes successfully."""
    type: EventType = EventType.STAGE_COMPLETE
    stage: int = 0
    stage_name: str = ""
    duration_ms: int = 0
    results_count: int = 0


@dataclass
class StageErrorEvent(StreamEvent):
    """Emitted when a stage fails."""
    type: EventType = EventType.STAGE_ERROR
    stage: int = 0
    stage_name: str = ""
    error: str = ""
    partial_results: int = 0
    can_continue: bool = False


@dataclass
class ModelStartEvent(StreamEvent):
    """Emitted when a model starts processing."""
    type: EventType = EventType.MODEL_START
    model: str = ""
    stage: int = 0


@dataclass
class ModelChunkEvent(StreamEvent):
    """Emitted for streaming content chunks."""
    type: EventType = EventType.MODEL_CHUNK
    model: str = ""
    stage: int = 0
    content: str = ""
    full_content: str = ""


@dataclass
class ModelCompleteEvent(StreamEvent):
    """Emitted when a model completes."""
    type: EventType = EventType.MODEL_COMPLETE
    model: str = ""
    stage: int = 0
    content: str = ""
    confidence: Optional[float] = None
    duration_ms: int = 0


@dataclass
class ModelErrorEvent(StreamEvent):
    """Emitted when a model fails."""
    type: EventType = EventType.MODEL_ERROR
    model: str = ""
    stage: int = 0
    error: str = ""
    error_code: Optional[str] = None
    retryable: bool = False


@dataclass
class ProgressEvent(StreamEvent):
    """Emitted to indicate overall progress."""
    type: EventType = EventType.PROGRESS
    stage: int = 0
    completed_models: int = 0
    total_models: int = 0
    percentage: float = 0.0


@dataclass
class DeliberationCompleteEvent(StreamEvent):
    """Emitted when entire deliberation completes."""
    type: EventType = EventType.DELIBERATION_COMPLETE
    total_duration_ms: int = 0
    stage1_count: int = 0
    stage2_count: int = 0
    has_synthesis: bool = False
    consensus_reached: bool = False


@dataclass
class DeliberationErrorEvent(StreamEvent):
    """Emitted when deliberation fails completely."""
    type: EventType = EventType.DELIBERATION_ERROR
    error: str = ""
    failed_stage: int = 0
    partial_results: Dict[str, Any] = None

    def __post_init__(self):
        self.partial_results = self.partial_results or {}
```

### 6.3 Implementation: Streaming Service

Create `backend/streaming/service.py`:

```python
"""Streaming service with robust error handling."""
import asyncio
import time
import logging
from typing import AsyncGenerator, Dict, Any, List, Optional

from .events import (
    StreamEvent,
    StageStartEvent,
    StageCompleteEvent,
    StageErrorEvent,
    ModelStartEvent,
    ModelChunkEvent,
    ModelCompleteEvent,
    ModelErrorEvent,
    ProgressEvent,
    DeliberationCompleteEvent,
    DeliberationErrorEvent
)
from ..openrouter import OpenRouterClient, OpenRouterError
from ..council import (
    parse_ranking_from_text,
    parse_confidence_from_response,
    calculate_aggregate_rankings,
    detect_consensus
)
from ..config import COUNCIL_MODELS, CHAIRMAN_MODEL

logger = logging.getLogger(__name__)


class StreamingDeliberationService:
    """
    Service for streaming council deliberation with proper error handling.

    Features:
    - Per-model error isolation
    - Stage-level error recovery
    - Partial result preservation
    - Detailed error events
    - Progress tracking
    """

    def __init__(
        self,
        client: OpenRouterClient = None,
        council_models: List[str] = None,
        chairman_model: str = None
    ):
        self.client = client or OpenRouterClient()
        self.council_models = council_models or COUNCIL_MODELS
        self.chairman_model = chairman_model or CHAIRMAN_MODEL

    async def stream_deliberation(
        self,
        question: str,
        include_confidence: bool = True,
        voting_method: str = "borda"
    ) -> AsyncGenerator[StreamEvent, None]:
        """
        Stream the entire deliberation process.

        Yields events for each stage, model, and error.
        Attempts to continue with partial results when possible.
        """
        start_time = time.time()
        stage1_results = []
        stage2_results = []
        stage3_result = None
        label_to_model = {}

        try:
            # ========== STAGE 1: Collect Responses ==========
            yield StageStartEvent(
                stage=1,
                stage_name="Response Collection",
                models=self.council_models
            )

            stage1_start = time.time()

            async for event in self._stream_stage1(question, include_confidence):
                yield event

                if isinstance(event, ModelCompleteEvent):
                    stage1_results.append({
                        "model": event.model,
                        "response": event.content,
                        "confidence": event.confidence
                    })

            if not stage1_results:
                yield StageErrorEvent(
                    stage=1,
                    stage_name="Response Collection",
                    error="No models responded successfully",
                    partial_results=0,
                    can_continue=False
                )
                yield self._create_error_complete(start_time, 1, stage1_results)
                return

            yield StageCompleteEvent(
                stage=1,
                stage_name="Response Collection",
                duration_ms=int((time.time() - stage1_start) * 1000),
                results_count=len(stage1_results)
            )

            # ========== STAGE 2: Peer Evaluation ==========
            if len(stage1_results) < 2:
                # Skip stage 2 if only one response
                yield StageErrorEvent(
                    stage=2,
                    stage_name="Peer Evaluation",
                    error="Insufficient responses for peer evaluation (need at least 2)",
                    partial_results=len(stage1_results),
                    can_continue=True
                )
            else:
                yield StageStartEvent(
                    stage=2,
                    stage_name="Peer Evaluation",
                    models=self.council_models
                )

                stage2_start = time.time()

                # Create anonymized mapping
                label_to_model = self._create_label_mapping(stage1_results)

                async for event in self._stream_stage2(
                    question, stage1_results, label_to_model
                ):
                    yield event

                    if isinstance(event, ModelCompleteEvent) and event.content:
                        parsed = parse_ranking_from_text(event.content)
                        stage2_results.append({
                            "model": event.model,
                            "ranking": event.content,
                            "parsed_ranking": parsed
                        })

                if stage2_results:
                    yield StageCompleteEvent(
                        stage=2,
                        stage_name="Peer Evaluation",
                        duration_ms=int((time.time() - stage2_start) * 1000),
                        results_count=len(stage2_results)
                    )
                else:
                    yield StageErrorEvent(
                        stage=2,
                        stage_name="Peer Evaluation",
                        error="No peer evaluations completed",
                        partial_results=0,
                        can_continue=True
                    )

            # ========== STAGE 3: Synthesis ==========
            yield StageStartEvent(
                stage=3,
                stage_name="Synthesis",
                models=[self.chairman_model]
            )

            stage3_start = time.time()

            # Calculate aggregate rankings
            aggregate_rankings = []
            if stage2_results and label_to_model:
                aggregate_rankings = calculate_aggregate_rankings(
                    stage2_results, label_to_model, voting_method
                )

            async for event in self._stream_stage3(
                question, stage1_results, stage2_results, aggregate_rankings
            ):
                yield event

                if isinstance(event, ModelCompleteEvent):
                    stage3_result = {
                        "model": event.model,
                        "response": event.content
                    }

            if stage3_result:
                yield StageCompleteEvent(
                    stage=3,
                    stage_name="Synthesis",
                    duration_ms=int((time.time() - stage3_start) * 1000),
                    results_count=1
                )
            else:
                yield StageErrorEvent(
                    stage=3,
                    stage_name="Synthesis",
                    error="Chairman synthesis failed",
                    partial_results=0,
                    can_continue=False
                )

            # ========== COMPLETE ==========
            consensus = None
            if stage2_results and label_to_model:
                consensus = detect_consensus(stage2_results, label_to_model)

            yield DeliberationCompleteEvent(
                total_duration_ms=int((time.time() - start_time) * 1000),
                stage1_count=len(stage1_results),
                stage2_count=len(stage2_results),
                has_synthesis=stage3_result is not None,
                consensus_reached=consensus.get("has_consensus", False) if consensus else False
            )

        except Exception as e:
            logger.exception("Unexpected error in deliberation")
            yield self._create_error_complete(start_time, 0, stage1_results, str(e))

    async def _stream_stage1(
        self,
        question: str,
        include_confidence: bool
    ) -> AsyncGenerator[StreamEvent, None]:
        """Stream Stage 1 responses from all models."""

        prompt = question
        if include_confidence:
            prompt += "\n\nAfter your response, rate your confidence (1-10):\nCONFIDENCE: X/10"

        tasks = []
        for model in self.council_models:
            task = asyncio.create_task(
                self._stream_single_model(model, prompt, stage=1)
            )
            tasks.append((model, task))

        completed = 0
        total = len(tasks)

        for model, task in tasks:
            yield ModelStartEvent(model=model, stage=1)

        for model, task in tasks:
            try:
                async for event in await task:
                    yield event

                    if isinstance(event, (ModelCompleteEvent, ModelErrorEvent)):
                        completed += 1
                        yield ProgressEvent(
                            stage=1,
                            completed_models=completed,
                            total_models=total,
                            percentage=(completed / total) * 100
                        )
            except Exception as e:
                completed += 1
                yield ModelErrorEvent(
                    model=model,
                    stage=1,
                    error=str(e),
                    retryable=True
                )

    async def _stream_single_model(
        self,
        model: str,
        prompt: str,
        stage: int
    ) -> AsyncGenerator[StreamEvent, None]:
        """Stream response from a single model."""
        start_time = time.time()
        full_content = ""

        try:
            async for chunk in self.client.stream(
                model=model,
                messages=[{"role": "user", "content": prompt}]
            ):
                if chunk["type"] == "content":
                    full_content = chunk["full_content"]
                    yield ModelChunkEvent(
                        model=model,
                        stage=stage,
                        content=chunk["content"],
                        full_content=full_content
                    )

                elif chunk["type"] == "error":
                    yield ModelErrorEvent(
                        model=model,
                        stage=stage,
                        error=chunk["error"],
                        retryable=True
                    )
                    return

            # Parse confidence if present
            confidence = None
            if full_content:
                _, confidence = parse_confidence_from_response(full_content)

            yield ModelCompleteEvent(
                model=model,
                stage=stage,
                content=full_content,
                confidence=confidence,
                duration_ms=int((time.time() - start_time) * 1000)
            )

        except OpenRouterError as e:
            yield ModelErrorEvent(
                model=model,
                stage=stage,
                error=str(e),
                error_code=type(e).__name__,
                retryable=isinstance(e, (ServerError, RateLimitError))
            )

    async def _stream_stage2(
        self,
        question: str,
        stage1_results: List[Dict],
        label_to_model: Dict[str, str]
    ) -> AsyncGenerator[StreamEvent, None]:
        """Stream Stage 2 peer evaluations."""
        # Build evaluation prompt
        model_to_label = {v: k for k, v in label_to_model.items()}

        responses_text = ""
        for result in stage1_results:
            label = model_to_label.get(result["model"], result["model"])
            responses_text += f"\n=== {label} ===\n{result['response']}\n"

        prompt = f"""Evaluate these responses to: {question}

{responses_text}

Rank them from best to worst. Provide your ranking as:
FINAL RANKING:
1. Response X
2. Response Y
...
"""

        # Stream from each model
        for model in self.council_models:
            yield ModelStartEvent(model=model, stage=2)

            async for event in self._stream_single_model(model, prompt, stage=2):
                yield event

    async def _stream_stage3(
        self,
        question: str,
        stage1_results: List[Dict],
        stage2_results: List[Dict],
        aggregate_rankings: List[Dict]
    ) -> AsyncGenerator[StreamEvent, None]:
        """Stream Stage 3 synthesis."""
        yield ModelStartEvent(model=self.chairman_model, stage=3)

        # Build synthesis prompt
        rankings_text = ""
        if aggregate_rankings:
            rankings_text = "Aggregate Rankings:\n"
            for i, r in enumerate(aggregate_rankings, 1):
                rankings_text += f"{i}. {r.get('model', 'Unknown')}\n"

        responses_text = ""
        for result in stage1_results:
            responses_text += f"\n=== {result['model']} ===\n{result['response']}\n"

        prompt = f"""Synthesize a final answer to: {question}

Individual Responses:
{responses_text}

{rankings_text}

Provide a comprehensive final answer, giving more weight to higher-ranked responses.
Do not mention the ranking process."""

        async for event in self._stream_single_model(
            self.chairman_model, prompt, stage=3
        ):
            yield event

    def _create_label_mapping(
        self,
        stage1_results: List[Dict]
    ) -> Dict[str, str]:
        """Create anonymous labels for models."""
        labels = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        return {
            f"Response {labels[i]}": result["model"]
            for i, result in enumerate(stage1_results)
            if i < len(labels)
        }

    def _create_error_complete(
        self,
        start_time: float,
        failed_stage: int,
        partial_results: List[Dict],
        error: str = "Deliberation failed"
    ) -> DeliberationErrorEvent:
        """Create error completion event with partial results."""
        return DeliberationErrorEvent(
            error=error,
            failed_stage=failed_stage,
            partial_results={
                "stage1_count": len(partial_results),
                "duration_ms": int((time.time() - start_time) * 1000)
            }
        )
```

---

## Phase 7: Model Configuration & Validation

### 7.1 Implementation

Create `backend/config/models.py`:

```python
"""Model configuration with validation."""
import os
import asyncio
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum

logger = logging.getLogger(__name__)


class ModelCapability(str, Enum):
    """Model capabilities."""
    TEXT = "text"
    VISION = "vision"
    FUNCTION_CALLING = "function_calling"
    REASONING = "reasoning"  # Extended thinking (o1, etc.)


@dataclass
class ModelConfig:
    """Configuration for a single model."""
    id: str                                    # e.g., "openai/gpt-4"
    display_name: str                          # e.g., "GPT-4"
    provider: str                              # e.g., "openai"

    # Capabilities
    capabilities: List[ModelCapability] = field(default_factory=list)
    context_window: int = 8192
    max_output_tokens: int = 4096

    # Rate limits
    requests_per_minute: int = 60
    tokens_per_minute: int = 100000

    # Pricing (per 1M tokens)
    input_price: float = 0.0
    output_price: float = 0.0

    # Custom settings
    default_temperature: float = 0.7
    supports_streaming: bool = True

    # Validation
    is_validated: bool = False
    last_validated: Optional[str] = None
    validation_error: Optional[str] = None


@dataclass
class CouncilConfig:
    """Configuration for the council."""
    council_models: List[ModelConfig] = field(default_factory=list)
    chairman_model: Optional[ModelConfig] = None
    fallback_models: List[ModelConfig] = field(default_factory=list)

    # Voting
    default_voting_method: str = "borda"

    # Timeouts
    default_timeout: int = 120

    @classmethod
    def from_env(cls) -> "CouncilConfig":
        """Load configuration from environment variables."""
        # Get model IDs from environment or use defaults
        council_ids = os.getenv("COUNCIL_MODELS", "").split(",")
        if not council_ids or council_ids == [""]:
            council_ids = DEFAULT_COUNCIL_MODELS

        chairman_id = os.getenv("CHAIRMAN_MODEL", DEFAULT_CHAIRMAN_MODEL)

        # Create model configs
        council = [
            ModelConfig(
                id=model_id.strip(),
                display_name=model_id.split("/")[-1],
                provider=model_id.split("/")[0] if "/" in model_id else "unknown"
            )
            for model_id in council_ids
            if model_id.strip()
        ]

        chairman = ModelConfig(
            id=chairman_id,
            display_name=chairman_id.split("/")[-1],
            provider=chairman_id.split("/")[0] if "/" in chairman_id else "unknown"
        )

        return cls(council_models=council, chairman_model=chairman)


# Default configuration
DEFAULT_COUNCIL_MODELS = [
    "anthropic/claude-opus-4",
    "openai/o1",
    "google/gemini-2.5-pro-preview-06-05",
    "deepseek/deepseek-r1",
    "openai/gpt-4.5",
]

DEFAULT_CHAIRMAN_MODEL = "anthropic/claude-opus-4"


class ConfigValidator:
    """Validates model configuration at startup."""

    def __init__(self, client):
        self.client = client
        self.results: Dict[str, Any] = {}

    async def validate_all(self, config: CouncilConfig) -> Dict[str, Any]:
        """Validate all configured models."""
        logger.info("Validating model configuration...")

        all_models = config.council_models + [config.chairman_model]
        if config.fallback_models:
            all_models.extend(config.fallback_models)

        tasks = [
            self._validate_model(model)
            for model in all_models
            if model
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        valid_count = sum(1 for r in results if r.get("valid", False))

        summary = {
            "total": len(all_models),
            "valid": valid_count,
            "invalid": len(all_models) - valid_count,
            "models": {
                model.id: results[i]
                for i, model in enumerate(all_models)
                if model
            }
        }

        if valid_count == 0:
            logger.error("No valid models configured!")
        elif valid_count < len(all_models):
            logger.warning(
                f"Some models invalid: {valid_count}/{len(all_models)} valid"
            )
        else:
            logger.info(f"All {valid_count} models validated successfully")

        return summary

    async def _validate_model(self, model: ModelConfig) -> Dict[str, Any]:
        """Validate a single model."""
        try:
            is_valid = await self.client.validate_model(model.id)

            model.is_validated = is_valid
            model.validation_error = None if is_valid else "Model not accessible"

            return {
                "valid": is_valid,
                "model": model.id,
                "error": model.validation_error
            }

        except Exception as e:
            model.is_validated = False
            model.validation_error = str(e)

            return {
                "valid": False,
                "model": model.id,
                "error": str(e)
            }


# Startup validation
async def validate_config_on_startup(client) -> CouncilConfig:
    """Validate configuration when application starts."""
    config = CouncilConfig.from_env()
    validator = ConfigValidator(client)

    results = await validator.validate_all(config)

    # Filter to only valid council models
    config.council_models = [
        m for m in config.council_models
        if m.is_validated
    ]

    if not config.council_models:
        raise RuntimeError("No valid council models available")

    if not config.chairman_model.is_validated:
        # Try to use first valid council model as chairman
        if config.council_models:
            logger.warning(
                f"Chairman model invalid, using {config.council_models[0].id}"
            )
            config.chairman_model = config.council_models[0]
        else:
            raise RuntimeError("No valid chairman model available")

    return config
```

---

## Phase 8: Council.py Refactoring

### 8.1 Target Structure

```
backend/
├── council/
│   ├── __init__.py              # Public API
│   ├── orchestrator.py          # Main coordination
│   ├── types.py                 # Type definitions
│   ├── prompts.py               # All prompts
│   ├── consensus.py             # Consensus detection
│   ├── voting/
│   │   ├── __init__.py
│   │   ├── base.py              # Base voting class
│   │   ├── borda.py             # Borda count
│   │   ├── mrr.py               # Mean Reciprocal Rank
│   │   ├── confidence.py        # Confidence-weighted
│   │   └── simple.py            # Simple average
│   ├── parsing/
│   │   ├── __init__.py
│   │   ├── ranking.py           # Ranking parser
│   │   ├── confidence.py        # Confidence parser
│   │   └── rubric.py            # Rubric parser
│   └── stages/
│       ├── __init__.py
│       ├── base.py              # Base stage class
│       ├── stage1.py            # Response collection
│       ├── stage2.py            # Peer evaluation
│       └── stage3.py            # Synthesis
```

### 8.2 Migration Strategy

1. **Create new modules** without modifying existing code
2. **Export from council/__init__.py** with same interface
3. **Update imports** in main.py gradually
4. **Deprecate old council.py** with compatibility layer
5. **Remove old code** after verification

This is detailed in the IMPLEMENTATION_PLAN.md Phase 4 section.

---

## Phase 9: Deployment Infrastructure

### 9.1 Docker Configuration

Create `Dockerfile`:

```dockerfile
# Backend Dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install uv for fast package management
RUN pip install uv

# Copy dependency files
COPY pyproject.toml .
COPY uv.lock .

# Install dependencies
RUN uv sync --frozen

# Copy application code
COPY backend/ backend/

# Create data directory
RUN mkdir -p data

# Expose port
EXPOSE 8001

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8001/ || exit 1

# Run application
CMD ["uv", "run", "python", "-m", "backend.main"]
```

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  backend:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "8001:8001"
    environment:
      - OPENROUTER_API_KEY=${OPENROUTER_API_KEY}
      - ENVIRONMENT=production
      - ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000
    volumes:
      - ./data:/app/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8001/"]
      interval: 30s
      timeout: 3s
      retries: 3

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "5173:80"
    depends_on:
      - backend
    environment:
      - VITE_API_URL=http://backend:8001
    restart: unless-stopped

volumes:
  data:
```

### 9.2 CI/CD Pipeline

Create `.github/workflows/ci.yml`:

```yaml
name: CI

on:
  push:
    branches: [main, master]
  pull_request:
    branches: [main, master]

jobs:
  backend-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install uv
        run: pip install uv

      - name: Install dependencies
        run: uv sync --dev

      - name: Run tests
        run: uv run pytest backend/tests/ -v --cov=backend --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          file: ./coverage.xml

  frontend-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'
          cache-dependency-path: frontend/package-lock.json

      - name: Install dependencies
        run: cd frontend && npm ci

      - name: Run tests
        run: cd frontend && npm test

      - name: Build
        run: cd frontend && npm run build

  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install ruff
        run: pip install ruff

      - name: Run linter
        run: ruff check backend/

  docker-build:
    runs-on: ubuntu-latest
    needs: [backend-test, frontend-test]
    steps:
      - uses: actions/checkout@v4

      - name: Build Docker images
        run: docker compose build
```

---

## Verification Checklist

### Phase 4: Authentication
- [ ] API key generation works
- [ ] Key validation rejects invalid keys
- [ ] Expired keys are rejected
- [ ] Revoked keys are rejected
- [ ] Permissions are enforced
- [ ] Audit logging captures all actions
- [ ] Rate limits are per-key
- [ ] Bootstrap script creates admin key

### Phase 5: OpenRouter Client
- [ ] Retry logic works for transient failures
- [ ] Rate limits are detected and respected
- [ ] Circuit breaker opens after failures
- [ ] Circuit breaker recovers after timeout
- [ ] Timeouts are configurable per-model
- [ ] All errors are properly classified
- [ ] Logging captures all operations

### Phase 6: Streaming Error Handling
- [ ] Stage-level errors are reported
- [ ] Model-level errors are isolated
- [ ] Partial results are preserved
- [ ] Progress events are accurate
- [ ] Error events include context
- [ ] Timeouts are handled gracefully

### Phase 7: Model Configuration
- [ ] Models are validated at startup
- [ ] Invalid models are filtered out
- [ ] Fallback models work
- [ ] Configuration from environment works
- [ ] Validation errors are logged

### Phase 8: Council Refactoring
- [ ] All modules under 300 lines
- [ ] Public API unchanged
- [ ] All tests still pass
- [ ] Type hints complete
- [ ] Documentation updated

### Phase 9: Deployment
- [ ] Docker build succeeds
- [ ] Docker compose works
- [ ] Health checks pass
- [ ] CI pipeline passes
- [ ] Production config documented

---

## Command Reference

```bash
# Run all tests
npm run test

# Run backend tests with coverage
uv run pytest backend/tests/ -v --cov=backend --cov-report=html

# Run frontend tests
cd frontend && npm test

# Bootstrap admin API key
uv run python -m backend.auth.bootstrap

# Validate model configuration
uv run python -m backend.config.validate

# Build Docker images
docker compose build

# Start with Docker
docker compose up -d

# View logs
docker compose logs -f backend

# Run linter
ruff check backend/

# Format code
ruff format backend/
```

---

## Timeline

| Week | Phase | Deliverables |
|------|-------|--------------|
| 1 | Phase 4 | Authentication system complete |
| 2 | Phase 5-6 | OpenRouter hardening, streaming errors |
| 3 | Phase 7-8 | Model config, council refactoring (start) |
| 4 | Phase 8 | Council refactoring (complete) |
| 5 | Phase 9 | Deployment infrastructure |
| 6 | Testing | Integration tests, documentation |

**Total: 6 weeks to 100% production-ready**

---

*This plan eliminates all quick fixes by providing complete, production-quality implementations with proper error handling, logging, testing, and documentation.*
