"""Health check endpoints."""

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, status
from pydantic import BaseModel

from app.config import get_settings

router = APIRouter()
logger = logging.getLogger(__name__)


class HealthResponse(BaseModel):
    """Health check response model."""

    status: str
    timestamp: str
    version: str
    uptime_seconds: float | None = None


class ReadyResponse(BaseModel):
    """Readiness check response model."""

    ready: bool
    checks: dict[str, bool]
    details: dict[str, Any] | None = None


# Track startup time
_startup_time: datetime | None = None


def set_startup_time() -> None:
    """Set the startup time for uptime calculation."""
    global _startup_time
    _startup_time = datetime.now(timezone.utc)


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Health check",
    description="Basic health check endpoint",
)
async def health_check() -> HealthResponse:
    """
    Perform a basic health check.
    
    Returns:
        HealthResponse: Current health status of the application.
    """
    settings = get_settings()
    now = datetime.now(timezone.utc)
    
    uptime = None
    if _startup_time:
        uptime = (now - _startup_time).total_seconds()

    return HealthResponse(
        status="healthy",
        timestamp=now.isoformat(),
        version=settings.app_version,
        uptime_seconds=uptime,
    )


@router.get(
    "/ready",
    response_model=ReadyResponse,
    status_code=status.HTTP_200_OK,
    summary="Readiness check",
    description="Check if the application is ready to serve requests",
)
async def readiness_check() -> ReadyResponse:
    """
    Perform a readiness check.
    
    Checks:
        - Memory manager availability
        - Model router availability
        - Tool registry availability
    
    Returns:
        ReadyResponse: Readiness status with individual check results.
    """
    checks: dict[str, bool] = {}
    details: dict[str, Any] = {}

    # Check memory manager
    try:
        from app.main import get_memory_manager
        memory_manager = get_memory_manager()
        checks["memory_manager"] = memory_manager is not None
    except Exception as e:
        checks["memory_manager"] = False
        details["memory_manager_error"] = str(e)

    # Check model router
    try:
        from app.main import get_model_router
        model_router = get_model_router()
        checks["model_router"] = model_router is not None
        if model_router:
            details["available_providers"] = model_router.list_providers()
    except Exception as e:
        checks["model_router"] = False
        details["model_router_error"] = str(e)

    # Check tool registry
    try:
        from app.main import get_tool_registry
        tool_registry = get_tool_registry()
        checks["tool_registry"] = tool_registry is not None
        if tool_registry:
            details["registered_tools"] = len(tool_registry.list_tools())
    except Exception as e:
        checks["tool_registry"] = False
        details["tool_registry_error"] = str(e)

    all_ready = all(checks.values())

    return ReadyResponse(
        ready=all_ready,
        checks=checks,
        details=details if details else None,
    )


@router.get(
    "/ping",
    status_code=status.HTTP_200_OK,
    summary="Ping endpoint",
    description="Simple ping endpoint for load balancers",
)
async def ping() -> dict[str, str]:
    """Simple ping endpoint."""
    return {"ping": "pong"}
