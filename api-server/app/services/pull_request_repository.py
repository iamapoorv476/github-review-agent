import structlog
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
import uuid

from app.models.pull_request import PullRequest

logger = structlog.get_logger()


async def upsert_pull_request(
    db: AsyncSession,
    repository_id: uuid.UUID,
    github_pr_id: int,
    pr_number: int,
    title: str,
    author_login: str,
    base_branch: str,
    head_branch: str,
    head_sha: str,
    pr_opened_at: datetime,
    files_changed: int = 0,
    lines_added: int = 0,
    lines_removed: int = 0,
) -> PullRequest:
    """
    Creates or updates a pull request record.
    Updates head_sha on each push — this is what allows
    re-reviews when new commits are pushed.
    """
    stmt = insert(PullRequest).values(
        repository_id=repository_id,
        github_pr_id=github_pr_id,
        pr_number=pr_number,
        title=title,
        author_login=author_login,
        base_branch=base_branch,
        head_branch=head_branch,
        head_sha=head_sha,
        pr_opened_at=pr_opened_at,
        files_changed=files_changed,
        lines_added=lines_added,
        lines_removed=lines_removed
    ).on_conflict_do_update(
        index_elements=["repository_id", "pr_number"],
        set_=dict(
            head_sha=head_sha,
            title=title,
            files_changed=files_changed,
            lines_added=lines_added,
            lines_removed=lines_removed
        )
    ).returning(PullRequest)

    result = await db.execute(stmt)
    pr = result.scalar_one()

    logger.info(
        "pull_request_upserted",
        pr_number=pr_number,
        head_sha=head_sha[:8]  # log only first 8 chars of SHA
    )

    return pr


async def get_pull_request(
    db: AsyncSession,
    repository_id: uuid.UUID,
    pr_number: int
) -> PullRequest | None:
    result = await db.execute(
        select(PullRequest).where(
            PullRequest.repository_id == repository_id,
            PullRequest.pr_number == pr_number
        )
    )
    return result.scalar_one_or_none()