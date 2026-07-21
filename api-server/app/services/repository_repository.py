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


async def register_repositories_from_install(
    db: AsyncSession,
    installation_id: uuid.UUID,
    repositories: list[dict],
) -> int:
    """
    Register repositories from an installation / installation_repositories
    webhook payload.

    These payloads carry only a MINIMAL repo object (id, name, full_name,
    private) — no owner object and no default_branch. So we derive owner from
    full_name and default the branch to "main". A later PR event fills in the
    real default_branch via upsert_repository().

    Crucially, on conflict we DO NOT touch default_branch or review_enabled:
    a repo may already carry the correct branch learned from a PR, and a repo
    an admin previously paused should stay paused. We also flip review_enabled
    back on, since re-adding a repo is an intent to review it again.

    Returns the number of repositories processed.
    """
    count = 0
    for repo in repositories:
        full_name = repo.get("full_name", "")
        owner = full_name.split("/")[0] if "/" in full_name else ""
        stmt = insert(Repository).values(
            installation_id=installation_id,
            github_repo_id=repo["id"],
            owner=owner,
            name=repo.get("name", ""),
            full_name=full_name,
            is_private=repo.get("private", False),
            default_branch="main",
            first_seen_at=datetime.now(timezone.utc),
            review_enabled=True,
            total_reviews=0,
            total_findings=0,
        ).on_conflict_do_update(
            index_elements=["github_repo_id"],
            set_=dict(
                installation_id=installation_id,
                owner=owner,
                name=repo.get("name", ""),
                full_name=full_name,
                is_private=repo.get("private", False),
                review_enabled=True,
                # NOTE: default_branch intentionally omitted — never clobber
                # a branch learned from a real PR event.
            ),
        )
        await db.execute(stmt)
        count += 1

    logger.info(
        "repositories_registered_from_install",
        installation_id=str(installation_id),
        count=count,
    )
    return count


async def disable_repositories_by_github_id(
    db: AsyncSession,
    github_repo_ids: list[int],
) -> int:
    """
    Soft-disable repositories removed from an installation.

    We set review_enabled=False rather than deleting, to preserve review
    history (same philosophy as deactivate_installation). Returns the count
    of rows matched.
    """
    if not github_repo_ids:
        return 0

    result = await db.execute(
        select(Repository).where(Repository.github_repo_id.in_(github_repo_ids))
    )
    repos = result.scalars().all()
    for repo in repos:
        repo.review_enabled = False

    logger.info(
        "repositories_disabled_from_install",
        github_repo_ids=github_repo_ids,
        matched=len(repos),
    )
    return len(repos)