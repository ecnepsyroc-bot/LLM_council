"""Business logic for API key management."""

import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional


def _utcnow() -> datetime:
    """Get current UTC time (timezone-aware)."""
    return datetime.now(timezone.utc)

from .exceptions import (
    ExpiredAPIKeyError,
    InsufficientPermissionsError,
    InvalidAPIKeyError,
    RevokedAPIKeyError,
)
from .models import (
    APIKeyCreate,
    APIKeyCreatedResponse,
    APIKeyResponse,
    AuthenticatedRequest,
    Permission,
)
from .repository import APIKeyRepository
from .utils import (
    extract_key_prefix,
    generate_api_key,
    is_valid_key_format,
    verify_api_key_auto,
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
            expires_at = _utcnow() + timedelta(days=request.expires_in_days)

        # Create in database
        db_key = self.repository.create(
            key_hash=key_hash,
            key_prefix=key_prefix,
            name=request.name,
            expires_at=expires_at,
            permissions=[p.value for p in request.permissions],
            rate_limit_override=request.rate_limit_override,
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
            rate_limit_override=db_key.rate_limit_override,
        )

    def validate_key(
        self,
        api_key: str,
        required_permission: Optional[Permission] = None,
        endpoint: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
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

        # Look up by prefix (bcrypt hashes are non-deterministic, so we can't lookup by hash)
        key_prefix = extract_key_prefix(api_key)
        db_key = self.repository.get_by_prefix(key_prefix)

        if not db_key:
            raise InvalidAPIKeyError()

        # Verify the key against stored hash (supports both bcrypt and legacy SHA-256)
        if not verify_api_key_auto(api_key, db_key.key_hash):
            raise InvalidAPIKeyError()

        # Check if revoked
        if not db_key.is_active:
            self.repository.log_usage(
                db_key.id, "revoked", endpoint, ip_address, user_agent
            )
            raise RevokedAPIKeyError()

        # Check expiration
        if db_key.expires_at and _utcnow() > db_key.expires_at:
            self.repository.log_usage(
                db_key.id, "expired", endpoint, ip_address, user_agent
            )
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
        self.repository.log_usage(
            db_key.id, "request", endpoint, ip_address, user_agent, request_id
        )

        # Update last used
        self.repository.update_last_used(db_key.id)

        # Return auth context
        return AuthenticatedRequest(
            api_key_id=db_key.id,
            key_prefix=db_key.key_prefix,
            permissions=[Permission(p) for p in db_key.permissions],
            rate_limit=db_key.rate_limit_override or self.default_rate_limit,
            request_id=request_id,
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
                rate_limit_override=k.rate_limit_override,
            )
            for k in db_keys
        ]

    def get_key(self, key_id: int) -> Optional[APIKeyResponse]:
        """Get a specific API key by ID (without sensitive data)."""
        db_key = self.repository.get_by_id(key_id)
        if not db_key:
            return None

        return APIKeyResponse(
            id=db_key.id,
            key_prefix=db_key.key_prefix,
            name=db_key.name,
            created_at=db_key.created_at,
            last_used_at=db_key.last_used_at,
            expires_at=db_key.expires_at,
            is_active=db_key.is_active,
            permissions=db_key.permissions,
            rate_limit_override=db_key.rate_limit_override,
        )

    def revoke_key(self, key_id: int) -> bool:
        """Revoke an API key."""
        return self.repository.revoke(key_id)

    def delete_key(self, key_id: int) -> bool:
        """Permanently delete an API key."""
        return self.repository.delete(key_id)
