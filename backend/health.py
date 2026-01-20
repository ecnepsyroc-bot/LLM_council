"""Health check endpoints for LLM Council."""

import logging
import time
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .config import OPENROUTER_API_KEY
from .database.connection import get_connection

logger = logging.getLogger(__name__)

_startup_time = time.time()
VERSION = "1.0.0"


class HealthResponse(BaseModel):
    status: str
    timestamp: str


class ReadinessResponse(BaseModel):
    status: str
    timestamp: str
    checks: dict


router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Basic liveness check."""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now(timezone.utc).isoformat()
    )


@router.get("/health/ready", response_model=ReadinessResponse)
async def readiness_check():
    """Readiness check for load balancers."""
    checks = {
        "database": False,
        "config": False,
    }
    all_healthy = True

    try:
        conn = get_connection()
        result = conn.execute("SELECT 1").fetchone()
        checks["database"] = result[0] == 1
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        checks["database"] = False
        all_healthy = False

    checks["config"] = bool(OPENROUTER_API_KEY)
    if not checks["config"]:
        all_healthy = False

    status = "ready" if all_healthy else "not_ready"

    if not all_healthy:
        raise HTTPException(status_code=503, detail={"status": status, "checks": checks})

    return ReadinessResponse(
        status=status,
        timestamp=datetime.now(timezone.utc).isoformat(),
        checks=checks
    )
