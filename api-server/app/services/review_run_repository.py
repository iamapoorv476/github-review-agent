import structlog
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import uuid

from app.models.review_run import ReviewRun
from app.models.pull_request import PullRequest
from app.models.repository import Repository

logger = structlog.get_logger()


async def count_reviews_today_for_installation(
    db: AsyncSession,
    installation_id: uuid.UUID,
) -> int:
    """
    Number of review runs queued since UTC midnight across all repos of an
    installation. Used by the daily cost cap — counts every run regardless
    of status, so failed runs still consume quota (they spent tokens too).
    """
    day_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    result = await db.execute(
        select(func.count())
        .select_from(ReviewRun)
        .join(PullRequest, ReviewRun.pull_request_id == PullRequest.id)
        .join(Repository, PullRequest.repository_id == Repository.id)
        .where(
            Repository.installation_id == installation_id,
            ReviewRun.queued_at >= day_start,
        )
    )
    return result.scalar_one()


async def create_review_run(
    db: AsyncSession,
    pull_request_id: uuid.UUID,
    trigger: str,
    idempotency_key: str,
    triggered_by: str | None = None,
) -> ReviewRun:
    """
    Creates a new review run with status 'queued'.
    Called before enqueueing the job — gives us a DB record
    to attach findings and reasoning steps to.
    """
    review_run = ReviewRun(
        pull_request_id=pull_request_id,
        trigger=trigger,
        triggered_by=triggered_by,
        status="queued",
        queued_at=datetime.now(timezone.utc),
        idempotency_key=idempotency_key
    )

    db.add(review_run)
    await db.flush()  # flush to get the generated UUID without committing

    logger.info(
        "review_run_created",
        review_run_id=str(review_run.id),
        pull_request_id=str(pull_request_id),
        trigger=trigger
    )

    return review_run


async def get_review_run(
    db: AsyncSession,
    review_run_id: uuid.UUID
) -> ReviewRun | None:
    result = await db.execute(
        select(ReviewRun).where(ReviewRun.id == review_run_id)
    )
    return result.scalar_one_or_none()


async def update_review_run_status(
    db: AsyncSession,
    review_run_id: uuid.UUID,
    status: str,
    error_message: str | None = None
) -> None:
    """
    Updates the status of a review run.
    Used by the worker to track job lifecycle.
    """
    review_run = await get_review_run(db, review_run_id)

    if not review_run:
        logger.error(
            "review_run_not_found",
            review_run_id=str(review_run_id)
        )
        return

    review_run.status = status

    if status == "processing":
        review_run.started_at = datetime.now(timezone.utc)

    if status in ("completed", "failed", "cancelled"):
        review_run.completed_at = datetime.now(timezone.utc)
        if review_run.started_at:
            delta = review_run.completed_at - review_run.started_at
            review_run.duration_ms = int(delta.total_seconds() * 1000)

    if error_message:
        review_run.error_message = error_message

    logger.info(
        "review_run_status_updated",
        review_run_id=str(review_run_id),
        status=status
    )