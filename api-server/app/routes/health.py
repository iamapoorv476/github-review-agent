import structlog
from fastapi import APIRouter
from pydantic import BaseModel

logger = structlog.get_logger()
router = APIRouter(tags=["health"])

class HealthResponse(BaseModel):
    status: str
    environment: str

class DeepHealthResponse(BaseModel):
    status: str
    check: dict[str, str]

@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Basic health check — Railway uses this to detect crashes.
    Must respond in under 1 second.
    """

    from app.config import get_settings
    settings = get_settings()

    return HealthResponse(
        status="ok",
        environment=settings.app_env
    )

@router.get("/health/deep", response_model= DeepHealthResponse)
async def deep_health_check():
    """
    Deep health check — verifies all dependencies are reachable.
    Use this to diagnose issues, not for Railway health monitoring.
    """

    checks = {}

    try:
        from app.database import get_db_status
        await get_db_status()
        checks["postgres"] = "ok"
    
    except Exception as e:
        logger.error("health_check_postgres_failed", error=str(e))
        checks["postgres"] = f"failed: {str(e)}"

    try:
        from app.utils.redis import get_redis_status
        await get_redis_status()
        checks["redis"] = "ok"
    except Exception as e:
        logger.error("health_check_redis_failed", error=str(e))
        checks["redis"] = f"failed: {str(e)}"
    
    overall = "ok" if all(
        v == "ok" for v in checks.values()
    ) else "degraded"

    return DeepHealthResponse(
        status=overall,
        checks=checks
    )
    
