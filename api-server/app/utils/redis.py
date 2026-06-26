import structlog
from redis.asyncio import Redis, ConnectionPool
from app.config import get_settings

logger = structlog.get_logger()

_pool: ConnectionPool | None = None


def get_redis_pool() -> ConnectionPool:
    """
    Returns the shared Redis connection pool.
    Creates it on first call (lazy initialization).
    """
    global _pool
    if _pool is None:
        settings = get_settings()
        _pool = ConnectionPool.from_url(
            settings.redis_url,
            max_connections=20,
            decode_responses=True
        )
        logger.info("redis_pool_created", url=settings.redis_url)
    return _pool


async def get_redis() -> Redis:
    """
    Returns an async Redis client using the shared pool.
    Use this as a FastAPI dependency.
    """
    return Redis(connection_pool=get_redis_pool())


async def get_redis_status() -> dict:
    """
    Health check — verifies Redis is reachable.
    """
    redis = await get_redis()
    result = await redis.ping()
    if not result:
        raise ConnectionError("Redis ping failed")
    return {"status": "ok"}