"""Pydantic models for authentication."""

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class Permission(str, Enum):
    """Available API key permissions."""

    READ = "read"  # Can read conversations
    WRITE = "write"  # Can create/modify conversations
    ADMIN = "admin"  # Can manage API keys
    STREAM = "stream"  # Can use streaming endpoints


class APIKeyCreate(BaseModel):
    """Request model for creating a new API key."""

    name: str = Field(
        ..., min_length=1, max_length=100, description="Human-readable name"
    )
    expires_in_days: Optional[int] = Field(
        None, ge=1, le=365, description="Days until expiration"
    )
    permissions: List[Permission] = Field(
        default=[Permission.READ, Permission.WRITE, Permission.STREAM],
        description="List of permissions",
    )
    rate_limit_override: Optional[int] = Field(
        None, ge=1, le=10000, description="Custom rate limit (requests per minute)"
    )


class APIKeyResponse(BaseModel):
    """Response model for API key operations (excludes sensitive data)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    key_prefix: str
    name: str
    created_at: datetime
    last_used_at: Optional[datetime]
    expires_at: Optional[datetime]
    is_active: bool
    permissions: List[str]
    rate_limit_override: Optional[int]


class APIKeyCreatedResponse(APIKeyResponse):
    """Response when a new API key is created (includes full key - shown once)."""

    api_key: str = Field(
        ..., description="Full API key - store securely, shown only once"
    )


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
