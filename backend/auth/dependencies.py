"""FastAPI dependency injection for authentication."""

from typing import Annotated, Optional

from fastapi import Depends, HTTPException, Request

from .exceptions import InsufficientPermissionsError
from .models import AuthenticatedRequest, Permission


def get_current_auth(request: Request) -> Optional[AuthenticatedRequest]:
    """
    Dependency to get current authentication context.

    Returns None if auth is bypassed (development mode).
    """
    auth = getattr(request.state, "auth", None)
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

    def dependency(
        auth: AuthenticatedRequest = Depends(require_auth),
    ) -> AuthenticatedRequest:
        if permission not in auth.permissions:
            raise InsufficientPermissionsError(permission.value)
        return auth

    return dependency


# Convenience type aliases
CurrentAuth = Annotated[Optional[AuthenticatedRequest], Depends(get_current_auth)]
RequiredAuth = Annotated[AuthenticatedRequest, Depends(require_auth)]
AdminAuth = Annotated[AuthenticatedRequest, Depends(require_permission(Permission.ADMIN))]
