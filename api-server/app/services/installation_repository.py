import structlog
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.models.installation import Installation

logger = structlog.get_logger()

async def upsert_installation(
        db: AsyncSession,
        github_install_id: int,
        account_login: str,
        account_type: str,
        account_avatar_url: str | None,
        installed_at: datetime,
) -> Installation:
    """
    Creates a new installation or updates an existing one.
    Uses PostgreSQL's ON CONFLICT for atomic upsert.
    """

    stmt = insert(Installation).values(
        github_install_id=github_install_id,
        account_login=account_login,
        account_type=account_type,
        account_avatar_url=account_avatar_url,
        installed_at=installed_at,
        is_active=True,
        review_enabled=True,
        review_categories=["security", "performance", "quality"]
    ). on_conflict_do_update(
        index_elements=["github_install_id"],
        set_=dict(
            account_login=account_login,
            account_avatar_url=account_avatar_url,
            is_active=True,
            uninstalled_at=None
        )
    ).returning(Installation)

    result = await db.execute(stmt)
    installation= result.scalar_one()

    logger.info(
        "installation_upserted",
        github_install_id=github_install_id,
        account_login=account_login
    )

    return installation

async def get_installation_by_github_id(
        db: AsyncSession,
        github_install_id: int
) -> Installation | None:
    """
    Fetches an installation by its GitHub installation ID.
    Returns None if not found.
    """

    result = await db.execute(
        select(Installation).where(
            Installation.github_install_id == github_install_id
        )
    )
    return result.scalar_one_or_none()

async def deactivate_installation(
    db: AsyncSession,
    github_install_id: int
) -> None:
    """
    Marks an installation as inactive when the app is uninstalled.
    Does NOT delete data — preserves review history.
    """
    installation = await get_installation_by_github_id(
        db, github_install_id
    )

    if installation:
        installation.is_active = False
        installation.uninstalled_at = datetime.now(timezone.utc)
        installation.access_token = None

        logger.info(
            "installation_deactivated",
            github_install_id=github_install_id,
            account_login=installation.account_login
        )
    else:
        logger.warning(
            "installation_not_found_on_deactivate",
            github_install_id=github_install_id
        )

