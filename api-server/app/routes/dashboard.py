"""
Dashboard read API — serves marginalia-web (Next.js, Phase 5).

Four endpoint groups, matching lib/data.ts fetchers one-to-one:

    GET   /api/stats                     → getStats()
    GET   /api/reviews                   → getReviews()
    GET   /api/reviews/{id}              → getReview(id)
    GET   /api/repos                     → getRepoSettings()
    PATCH /api/repos/{id}                → saveRepoSettings()
    PATCH /api/installations/{id}        → org-level toggles

All endpoints are read-mostly and unauthenticated for local development.
Before deploying, put these behind your dashboard auth (session cookie
or a shared token) — they expose review content for every tenant.
"""
import uuid
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db_session
from app.models import (
    Finding,
    Installation,
    PullRequest,
    ReasoningStep,
    ReviewRun,
    Repository,
)
from app.schemas.dashboard import (
    FindingOut,
    InstallationSettingsUpdate,
    PullRequestRef,
    ReasoningStepOut,
    RepoRef,
    RepoSettings,
    RepoSettingsUpdate,
    ReviewDetail,
    ReviewListResponse,
    ReviewSummary,
    SeverityBreakdown,
    StatsResponse,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/api", tags=["dashboard"])


# ---------------------------------------------------------------- helpers

def _review_summary_kwargs(run: ReviewRun, step_count: int = 0) -> dict:
    """Shared field mapping for ReviewSummary and ReviewDetail."""
    return dict(
        id=run.id,
        status=run.status,
        trigger=run.trigger,
        triggered_by=run.triggered_by,
        queued_at=run.queued_at,
        started_at=run.started_at,
        completed_at=run.completed_at,
        duration_ms=run.duration_ms,
        model_used=run.model_used,
        input_tokens=run.input_tokens,
        output_tokens=run.output_tokens,
        total_cost_usd=float(run.total_cost_usd) if run.total_cost_usd is not None else None,
        tool_calls_made=run.tool_calls_made,
        findings_count=run.findings_count,
        critical_count=run.critical_count,
        high_count=run.high_count,
        medium_count=run.medium_count,
        low_count=run.low_count,
        reasoning_step_count=step_count,
        review_comment_url=run.review_comment_url,
        pull_request=PullRequestRef.model_validate(run.pull_request),
        repository=RepoRef.model_validate(run.pull_request.repository),
    )


def _parse_uuid(value: str, what: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid {what} id")


# ---------------------------------------------------------------- stats

@router.get("/stats", response_model=StatsResponse)
async def get_stats(db: AsyncSession = Depends(get_db_session)):
    """Aggregate numbers for the dashboard header strip."""

    status_rows = (await db.execute(
        select(ReviewRun.status, func.count())
        .group_by(ReviewRun.status)
    )).all()
    by_status = {status: count for status, count in status_rows}

    severity_rows = (await db.execute(
        select(Finding.severity, func.count())
        .group_by(Finding.severity)
    )).all()
    by_severity = {sev: count for sev, count in severity_rows}

    median_ms = (await db.execute(
        select(
            func.percentile_cont(0.5).within_group(ReviewRun.duration_ms)
        ).where(
            ReviewRun.status == "completed",
            ReviewRun.duration_ms.isnot(None),
        )
    )).scalar_one_or_none()

    totals = (await db.execute(
        select(
            func.coalesce(func.sum(ReviewRun.total_cost_usd), 0),
            func.coalesce(
                func.sum(ReviewRun.input_tokens + ReviewRun.output_tokens), 0
            ),
        )
    )).one()

    repos_active = (await db.execute(
        select(func.count()).select_from(Repository)
        .where(Repository.review_enabled.is_(True))
    )).scalar_one()

    return StatsResponse(
        reviews_total=sum(by_status.values()),
        reviews_completed=by_status.get("completed", 0),
        reviews_failed=by_status.get("failed", 0),
        reviews_running=by_status.get("queued", 0) + by_status.get("processing", 0),
        findings_total=sum(by_severity.values()),
        findings_by_severity=SeverityBreakdown(
            critical=by_severity.get("critical", 0),
            high=by_severity.get("high", 0),
            medium=by_severity.get("medium", 0),
            low=by_severity.get("low", 0),
        ),
        median_review_ms=int(median_ms) if median_ms is not None else None,
        repos_active=repos_active,
        total_cost_usd=float(totals[0]),
        total_tokens=int(totals[1]),
    )


# ---------------------------------------------------------------- reviews

@router.get("/reviews", response_model=ReviewListResponse)
async def list_reviews(
    status: Optional[str] = Query(default=None, description="queued|processing|completed|failed|cancelled"),
    repo: Optional[str] = Query(default=None, description="Repository full_name, e.g. acme/payments"),
    severity: Optional[str] = Query(default=None, description="Only runs with ≥1 finding of this severity"),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db_session),
):
    """Review history, newest first — powers the reviews ledger."""

    filters = []
    if status:
        filters.append(ReviewRun.status == status)
    if severity:
        column = {
            "critical": ReviewRun.critical_count,
            "high": ReviewRun.high_count,
            "medium": ReviewRun.medium_count,
            "low": ReviewRun.low_count,
        }.get(severity)
        if column is None:
            raise HTTPException(status_code=400, detail="Invalid severity filter")
        filters.append(column > 0)

    base = (
        select(ReviewRun)
        .join(ReviewRun.pull_request)
        .join(PullRequest.repository)
    )
    if repo:
        filters.append(Repository.full_name == repo)
    if filters:
        base = base.where(*filters)

    total = (await db.execute(
        select(func.count()).select_from(base.subquery())
    )).scalar_one()

    runs = (await db.execute(
        base
        .options(
            selectinload(ReviewRun.pull_request)
            .selectinload(PullRequest.repository)
        )
        .order_by(ReviewRun.queued_at.desc())
        .limit(limit)
        .offset(offset)
    )).scalars().all()

    # One grouped query for step counts across the page — avoids N+1
    run_ids = [r.id for r in runs]
    step_counts: dict = {}
    if run_ids:
        rows = (await db.execute(
            select(ReasoningStep.review_run_id, func.count())
            .where(ReasoningStep.review_run_id.in_(run_ids))
            .group_by(ReasoningStep.review_run_id)
        )).all()
        step_counts = {rid: count for rid, count in rows}

    return ReviewListResponse(
        items=[
            ReviewSummary(**_review_summary_kwargs(r, step_counts.get(r.id, 0)))
            for r in runs
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/reviews/{review_id}", response_model=ReviewDetail)
async def get_review(
    review_id: str,
    db: AsyncSession = Depends(get_db_session),
):
    """One review run with findings and the full reasoning trace."""

    run_id = _parse_uuid(review_id, "review")

    run = (await db.execute(
        select(ReviewRun)
        .where(ReviewRun.id == run_id)
        .options(
            selectinload(ReviewRun.pull_request)
            .selectinload(PullRequest.repository),
            selectinload(ReviewRun.findings),
            selectinload(ReviewRun.reasoning_steps),
        )
    )).scalar_one_or_none()

    if run is None:
        raise HTTPException(status_code=404, detail="Review not found")

    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    findings = sorted(
        run.findings,
        key=lambda f: (severity_order.get(f.severity, 9), f.file_path, f.line_number or 0),
    )

    return ReviewDetail(
        **_review_summary_kwargs(run, len(run.reasoning_steps)),
        error_message=run.error_message,
        retry_count=run.retry_count,
        findings=[FindingOut.model_validate(f) for f in findings],
        reasoning_steps=[
            ReasoningStepOut.model_validate(s) for s in run.reasoning_steps
        ],
    )


# ---------------------------------------------------------------- repos

def _repo_settings(repo: Repository) -> RepoSettings:
    return RepoSettings(
        id=repo.id,
        installation_id=repo.installation_id,
        full_name=repo.full_name,
        owner=repo.owner,
        name=repo.name,
        is_private=repo.is_private,
        default_branch=repo.default_branch,
        review_enabled=repo.review_enabled,
        total_reviews=repo.total_reviews,
        total_findings=repo.total_findings,
        last_reviewed_at=repo.last_reviewed_at,
        account_login=repo.installation.account_login,
        review_categories=repo.installation.review_categories,
    )


@router.get("/repos", response_model=list[RepoSettings])
async def list_repos(db: AsyncSession = Depends(get_db_session)):
    """All repositories with their settings — powers the settings page."""

    repos = (await db.execute(
        select(Repository)
        .options(selectinload(Repository.installation))
        .order_by(Repository.full_name)
    )).scalars().all()

    return [_repo_settings(r) for r in repos]


@router.patch("/repos/{repo_id}", response_model=RepoSettings)
async def update_repo(
    repo_id: str,
    body: RepoSettingsUpdate,
    db: AsyncSession = Depends(get_db_session),
):
    """Toggle per-repo settings from the dashboard."""

    rid = _parse_uuid(repo_id, "repository")

    repo = (await db.execute(
        select(Repository)
        .where(Repository.id == rid)
        .options(selectinload(Repository.installation))
    )).scalar_one_or_none()

    if repo is None:
        raise HTTPException(status_code=404, detail="Repository not found")

    if body.review_enabled is not None:
        repo.review_enabled = body.review_enabled

    await db.flush()
    logger.info(
        "repo_settings_updated",
        repo=repo.full_name,
        review_enabled=repo.review_enabled,
    )
    return _repo_settings(repo)


@router.patch("/installations/{installation_id}")
async def update_installation(
    installation_id: str,
    body: InstallationSettingsUpdate,
    db: AsyncSession = Depends(get_db_session),
):
    """Org-level toggles: master switch and finding categories."""

    iid = _parse_uuid(installation_id, "installation")

    installation = (await db.execute(
        select(Installation).where(Installation.id == iid)
    )).scalar_one_or_none()

    if installation is None:
        raise HTTPException(status_code=404, detail="Installation not found")

    if body.review_enabled is not None:
        installation.review_enabled = body.review_enabled

    if body.review_categories is not None:
        valid = {"security", "performance", "quality"}
        invalid = set(body.review_categories) - valid
        if invalid:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid categories: {sorted(invalid)}",
            )
        installation.review_categories = body.review_categories

    await db.flush()
    logger.info(
        "installation_settings_updated",
        account=installation.account_login,
        review_enabled=installation.review_enabled,
        categories=installation.review_categories,
    )
    return {
        "id": str(installation.id),
        "account_login": installation.account_login,
        "review_enabled": installation.review_enabled,
        "review_categories": installation.review_categories,
    }