"""
Health check endpoints for LLM Council.

Endpoints:
- GET /health - Basic liveness (always 200 if running)
- GET /health/ready - Readiness (DB connected, etc.)
- GET /health/detailed - Full status (requires admin auth)
"""

import logging
import time
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from .database.connection import get_connection
from .settings import get_settings

logger = logging.getLogger(__name__)

# Track startup time
_startup_time = time.time()

# Version info (should be set during build)
VERSION = "1.0.0"


class HealthResponse(BaseModel):
    """Basic health response."""
    status: str
    timestamp: str


class ReadinessResponse(BaseModel):
    """Readiness check response."""
    status: str
    timestamp: str
    checks: dict


class DetailedHealthResponse(BaseModel):
    """Detailed health response (admin only)."""
    status: str
    version: str
    timestamp: str
    uptime_seconds: int
    database: dict
    openrouter: dict
    config: dict


router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Basic liveness check.

    Returns 200 if the service is running.
    This endpoint should always succeed if the application started.
    """
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now(timezone.utc).isoformat()
    )


@router.get("/health/ready", response_model=ReadinessResponse)
async def readiness_check():
    """
    Readiness check for load balancers.

    Verifies that critical dependencies are available:
    - Database connection works
    - Required configuration is present
    """
    checks = {
        "database": False,
        "config": False,
    }
    all_healthy = True

    # Check database
    try:
        conn = get_connection()
        result = conn.execute("SELECT 1").fetchone()
        checks["database"] = result[0] == 1
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        checks["database"] = False
        all_healthy = False

    # Check configuration
    try:
        settings = get_settings()
        checks["config"] = bool(settings.openrouter_api_key)
    except Exception as e:
        logger.error(f"Config health check failed: {e}")
        checks["config"] = False
        all_healthy = False

    status = "ready" if all_healthy else "not_ready"

    if not all_healthy:
        raise HTTPException(status_code=503, detail={"status": status, "checks": checks})

    return ReadinessResponse(
        status=status,
        timestamp=datetime.now(timezone.utc).isoformat(),
        checks=checks
    )


@router.get("/health/detailed", response_model=DetailedHealthResponse)
async def detailed_health_check(request: Request):
    """
    Detailed health status (admin only).

    Provides comprehensive health information including:
    - Database statistics
    - OpenRouter connectivity
    - Configuration summary
    """
    # Check for admin authentication
    auth = getattr(request.state, 'auth', None)

    # In bypass mode or if authenticated as admin, allow access
    settings = get_settings()
    if not settings.bypass_auth:
        if not auth:
            raise HTTPException(status_code=401, detail="Authentication required")
        # Check for admin permission
        if hasattr(auth, 'permissions') and 'admin' not in [p.value if hasattr(p, 'value') else p for p in auth.permissions]:
            raise HTTPException(status_code=403, detail="Admin permission required")

    # Collect database stats
    db_stats = {
        "connected": False,
        "conversations": 0,
        "messages": 0,
        "api_keys": 0,
    }

    try:
        conn = get_connection()
        db_stats["connected"] = True
        db_stats["conversations"] = conn.execute("SELECT COUNT(*) FROM conversations").fetchone()[0]
        db_stats["messages"] = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]

        # Try to get API key count (table might not exist in older schemas)
        try:
            db_stats["api_keys"] = conn.execute("SELECT COUNT(*) FROM api_keys").fetchone()[0]
        except Exception:
            db_stats["api_keys"] = 0

    except Exception as e:
        logger.error(f"Database stats collection failed: {e}")

    # OpenRouter status
    openrouter_status = {
        "configured": bool(settings.openrouter_api_key),
        "last_check": None,
    }

    # Configuration summary (redacted)
    config_summary = settings.to_safe_dict()

    # Calculate uptime
    uptime = int(time.time() - _startup_time)

    # Determine overall status
    status = "healthy" if db_stats["connected"] and openrouter_status["configured"] else "degraded"

    return DetailedHealthResponse(
        status=status,
        version=VERSION,
        timestamp=datetime.now(timezone.utc).isoformat(),
        uptime_seconds=uptime,
        database=db_stats,
        openrouter=openrouter_status,
        config=config_summary
    )


def set_version(version: str):
    """Set the application version (called during startup)."""
    global VERSION
    VERSION = version
