"""FastAPI authentication middleware."""

import logging
import os
from typing import Optional

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware

from .exceptions import AuthenticationError
from .models import Permission
from .service import APIKeyService

logger = logging.getLogger(__name__)


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
        "/health",
    }

    # Path prefixes that don't require authentication
    PUBLIC_PREFIXES = (
        "/docs",
        "/redoc",
    )

    def __init__(self, app, service: Optional[APIKeyService] = None, bypass_auth: bool = False):
        super().__init__(app)
        self.service = service or APIKeyService()
        self.bypass_auth = bypass_auth or os.getenv("BYPASS_AUTH", "").lower() == "true"

    async def dispatch(self, request: Request, call_next):
        # Skip auth for public paths
        if self._is_public_path(request.url.path):
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
                headers={"WWW-Authenticate": "ApiKey"},
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
                user_agent=request.headers.get("user-agent"),
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
            logger.error(f"Authentication error: {e}")
            raise HTTPException(status_code=500, detail="Authentication service error")

    def _is_public_path(self, path: str) -> bool:
        """Check if the path is public (doesn't require authentication)."""
        if path in self.PUBLIC_PATHS:
            return True
        for prefix in self.PUBLIC_PREFIXES:
            if path.startswith(prefix):
                return True
        return False

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

        # Admin endpoints require ADMIN permission
        if "/api/keys" in request.url.path:
            return Permission.ADMIN

        # Write operations
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            return Permission.WRITE

        # Read operations
        return Permission.READ
