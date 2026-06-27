import structlog
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    create_async_engine,
    async_sessionmaker
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text

logger = structlog.get_logger()

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker | None = None

class Base(DeclarativeBase):
    """
    Base class for all SQLAlchemy models.
    Every model inherits from this.
    """
    pass

def get_engine() -> AsyncEngine:
    """
    Returns the shared async database engine.
    Creates it on first call (lazy initialization).
    """
    global _engine
    if _engine is None:
        from app.config import get_settings
        settings = get_settings()

        _engine = create_async_engine(
            settings.database_url,
            echo=settings.is_development,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True
        )
        logger.info("database_engine_created")
    return _engine

def get_session_factory() -> async_sessionmaker:
    """
    Returns the shared session factory.
    Use this to create database sessions.
    """
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False  # prevents lazy loading issues
        )
    return _session_factory


async def get_db_session() -> AsyncSession:
    """
    FastAPI dependency — provides a database session per request.
    Automatically commits on success, rolls back on exception.

    Usage in route:
        async def my_route(db: AsyncSession = Depends(get_db_session)):
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

async def get_db_status() -> dict:
    """
    Health check — verifies database is reachable.
    Replaces the placeholder in health routes.
    """
    engine = get_engine()
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    return {"status": "ok"}