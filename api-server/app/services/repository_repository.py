import structlog
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
import uuid

from app.models.repository import Repository

logger = structlog.get_logger()


async def upsert_repository(
    db: AsyncSession,
    installation_id: uuid.UUID,
    github_repo_id: int,
    owner: str,
    name: str,
    full_name: str,
    is_private: bool,
    default_branch: str,
) -> Repository:
    """
    Creates a new repository record or updates an existing one.
    Repositories are created lazily — on first webhook, not on install.
    """
    stmt = insert(Repository).values(
        installation_id=installation_id,
        github_repo_id=github_repo_id,
        owner=owner,
        name=name,
        full_name=full_name,
        is_private=is_private,
        default_branch=default_branch,
        first_seen_at=datetime.now(timezone.utc),
        review_enabled=True,
        total_reviews=0,
        total_findings=0
    ).on_conflict_do_update(
        index_elements=["github_repo_id"],
        set_=dict(
            owner=owner,
            name=name,
            full_name=full_name,
            default_branch=default_branch,
            is_private=is_private
        )
    ).returning(Repository)

    result = await db.execute(stmt)
    repository = result.scalar_one()

    logger.info(
        "repository_upserted",
        github_repo_id=github_repo_id,
        full_name=full_name
    )

    return repository