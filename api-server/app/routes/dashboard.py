import uuid
import structlog
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case

from app.database import get_db_session
from app.models.installation import Installation
from app.models.repository import Repository
from app.models.pull_request import PullRequest
from app.models.review_run import ReviewRun
from app.models.finding import Finding
from app.models.reasoning_step import ReasoningStep

logger = structlog.get_logger()
router = APIRouter(tags=["dashboard"])


# ─────────────────────────────────────────────
# Auth dependency (optional — imported from middleware)
# ─────────────────────────────────────────────
async def optional_installation(
    request=None,
    db: AsyncSession = Depends(get_db_session),
) -> Optional[Installation]:
    """
    Returns Installation if a valid Bearer gra_... key is present,
    None otherwise (public / demo mode).
    """
    from fastapi import Request
    from app.services.api_key import resolve_api_key

    if request is None:
        return None

    auth = request.headers.get("Authorization", "")
    if not auth:
        return None

    scheme, _, token = auth.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(
            status_code=401,
            detail="Expected 'Authorization: Bearer <api key>'"
        )

    installation = await resolve_api_key(db, token.strip())
    if installation is None:
        logger.warning("api_key_rejected", key_prefix=token.strip()[:8])
        raise HTTPException(status_code=401, detail="Invalid or revoked API key")

    return installation


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────
def _parse_uuid(value: str, what: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=422,
            detail=f"Invalid {what}: {value!r}"
        )


def _verdict(run: ReviewRun) -> str:
    if run.status == "processing":
        return "reviewing"
    if run.status == "failed":
        return "failed"
    if run.status == "queued":
        return "queued"
    if run.findings_count == 0:
        return "approved"
    if run.critical_count > 0 or run.high_count > 0:
        return "changes_requested"
    return "commented"


def _duration_str(ms: Optional[int]) -> str:
    if not ms:
        return "0m 00s"
    minutes = ms // 60000
    seconds = (ms % 60000) // 1000
    return f"{minutes}m {seconds:02d}s"


# ─────────────────────────────────────────────
# GET /api/stats
# ─────────────────────────────────────────────
@router.get("/api/stats")
async def get_stats(
    db: AsyncSession = Depends(get_db_session),
    installation: Optional[Installation] = Depends(optional_installation),
):
    """Aggregate dashboard metrics."""

    base = select(ReviewRun)
    if installation:
        base = (
            base
            .join(PullRequest, ReviewRun.pull_request_id == PullRequest.id)
            .join(Repository, PullRequest.repository_id == Repository.id)
            .where(Repository.installation_id == installation.id)
        )

    result = await db.execute(base)
    runs = result.scalars().all()

    total = len(runs)
    running = sum(1 for r in runs if r.status == "processing")
    failed = sum(1 for r in runs if r.status == "failed")
    completed = [r for r in runs if r.status == "completed"]

    total_findings = sum(r.findings_count or 0 for r in completed)
    critical_count = sum(r.critical_count or 0 for r in completed)
    high_count = sum(r.high_count or 0 for r in completed)
    warning_count = high_count
    suggestion_count = sum(r.low_count or 0 for r in completed)

    durations = [r.duration_ms for r in completed if r.duration_ms]
    median_ms = sorted(durations)[len(durations) // 2] if durations else 0

    total_cost = sum(
        float(r.total_cost_usd or 0) for r in completed
    )

    # Active repos
    repo_query = select(func.count(Repository.id.distinct()))
    if installation:
        repo_query = repo_query.where(
            Repository.installation_id == installation.id
        )
    repo_result = await db.execute(repo_query)
    active_repos = repo_result.scalar() or 0

    return {
        "total_reviews": total,
        "running": running,
        "failed": failed,
        "total_findings": total_findings,
        "critical_count": critical_count,
        "high_count": high_count,
        "warning_count": warning_count,
        "suggestion_count": suggestion_count,
        "median_review_time_ms": median_ms,
        "median_review_time": _duration_str(median_ms),
        "total_cost_usd": round(total_cost, 4),
        "active_repos": active_repos,
    }


# ─────────────────────────────────────────────
# GET /api/reviews
# ─────────────────────────────────────────────
@router.get("/api/reviews")
async def list_reviews(
    limit: int = 20,
    offset: int = 0,
    status: Optional[str] = None,
    repo: Optional[str] = None,
    db: AsyncSession = Depends(get_db_session),
    installation: Optional[Installation] = Depends(optional_installation),
):
    """List review runs with PR and repo metadata."""

    query = (
        select(ReviewRun, PullRequest, Repository)
        .join(PullRequest, ReviewRun.pull_request_id == PullRequest.id)
        .join(Repository, PullRequest.repository_id == Repository.id)
        .order_by(ReviewRun.queued_at.desc())
    )

    if installation:
        query = query.where(Repository.installation_id == installation.id)
    if status:
        query = query.where(ReviewRun.status == status)
    if repo:
        query = query.where(Repository.full_name == repo)

    # Reasoning step counts
    step_counts_q = select(
        ReasoningStep.review_run_id,
        func.count(ReasoningStep.id).label("step_count")
    ).group_by(ReasoningStep.review_run_id).subquery()

    query = (
        query
        .outerjoin(
            step_counts_q,
            ReviewRun.id == step_counts_q.c.review_run_id
        )
        .add_columns(step_counts_q.c.step_count)
        .limit(limit)
        .offset(offset)
    )

    result = await db.execute(query)
    rows = result.all()

    reviews = []
    for row in rows:
        run, pr, repo_obj = row[0], row[1], row[2]
        step_count = row[3] or 0

        reviews.append({
            "id": str(run.id),
            "status": run.status,
            "verdict": _verdict(run),
            "trigger": run.trigger,
            "triggered_by": run.triggered_by,

            # PR info
            "pr_number": pr.pr_number,
            "pr_title": pr.title,
            "pr_author": pr.author_login,
            "head_sha": pr.head_sha,

            # Repo info
            "repo_full_name": repo_obj.full_name,
            "repo_owner": repo_obj.owner,
            "repo_name": repo_obj.name,

            # Findings
            "findings_count": run.findings_count or 0,
            "critical_count": run.critical_count or 0,
            "high_count": run.high_count or 0,
            "medium_count": run.medium_count or 0,
            "low_count": run.low_count or 0,

            # Timing & cost
            "queued_at": run.queued_at.isoformat() if run.queued_at else None,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            "duration_ms": run.duration_ms,
            "duration_str": _duration_str(run.duration_ms),

            # LLM
            "model_used": run.model_used,
            "input_tokens": run.input_tokens or 0,
            "output_tokens": run.output_tokens or 0,
            "total_cost_usd": float(run.total_cost_usd or 0),

            # Trace
            "reasoning_steps": step_count,
            "files_changed": pr.files_changed or 0,

            # GitHub
            "github_review_id": run.github_review_id,
            "review_comment_url": run.review_comment_url,
            "error_message": run.error_message,
            "retry_count": run.retry_count or 0,
        })

    return {"reviews": reviews, "total": len(reviews), "limit": limit, "offset": offset}


# ─────────────────────────────────────────────
# GET /api/reviews/{review_run_id}
# ─────────────────────────────────────────────
@router.get("/api/reviews/{review_run_id}")
async def get_review(
    review_run_id: str,
    db: AsyncSession = Depends(get_db_session),
    installation: Optional[Installation] = Depends(optional_installation),
):
    """Full review detail with findings."""
    run_id = _parse_uuid(review_run_id, "review_run_id")

    result = await db.execute(
        select(ReviewRun, PullRequest, Repository)
        .join(PullRequest, ReviewRun.pull_request_id == PullRequest.id)
        .join(Repository, PullRequest.repository_id == Repository.id)
        .where(ReviewRun.id == run_id)
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Review run not found")

    run, pr, repo_obj = row

    if installation and repo_obj.installation_id != installation.id:
        raise HTTPException(status_code=404, detail="Review run not found")

    # Findings
    findings_result = await db.execute(
        select(Finding)
        .where(Finding.review_run_id == run_id)
        .order_by(Finding.severity, Finding.file_path)
    )
    findings = findings_result.scalars().all()

    # Reasoning steps
    steps_result = await db.execute(
        select(ReasoningStep)
        .where(ReasoningStep.review_run_id == run_id)
        .order_by(ReasoningStep.step_number)
    )
    steps = steps_result.scalars().all()

    return {
        "id": str(run.id),
        "status": run.status,
        "verdict": _verdict(run),
        "trigger": run.trigger,
        "triggered_by": run.triggered_by,

        "pr_number": pr.pr_number,
        "pr_title": pr.title,
        "pr_author": pr.author_login,
        "head_sha": pr.head_sha,
        "base_branch": pr.base_branch,
        "head_branch": pr.head_branch,

        "repo_full_name": repo_obj.full_name,
        "repo_owner": repo_obj.owner,
        "repo_name": repo_obj.name,

        "findings_count": run.findings_count or 0,
        "critical_count": run.critical_count or 0,
        "high_count": run.high_count or 0,
        "medium_count": run.medium_count or 0,
        "low_count": run.low_count or 0,

        "queued_at": run.queued_at.isoformat() if run.queued_at else None,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "duration_ms": run.duration_ms,
        "duration_str": _duration_str(run.duration_ms),

        "model_used": run.model_used,
        "input_tokens": run.input_tokens or 0,
        "output_tokens": run.output_tokens or 0,
        "total_cost_usd": float(run.total_cost_usd or 0),

        "github_review_id": run.github_review_id,
        "review_comment_url": run.review_comment_url,
        "error_message": run.error_message,

        "findings": [
            {
                "id": str(f.id),
                "severity": f.severity,
                "category": f.category,
                "title": f.title,
                "description": f.description,
                "suggestion": f.suggestion,
                "file_path": f.file_path,
                "line_number": f.line_number,
                "diff_position": f.diff_position,
                "code_snippet": f.code_snippet,
                "was_posted": f.was_posted,
                "post_failed": f.post_failed,
                "github_comment_id": f.github_comment_id,
            }
            for f in findings
        ],

        "reasoning_steps": [
            {
                "step_number": s.step_number,
                "step_type": s.step_type,
                "content": s.content,
                "tool_name": s.tool_name,
                "tool_input": s.tool_input,
                "tool_output_summary": s.tool_output_summary,
                "tokens_used": s.tokens_used,
                "duration_ms": s.duration_ms,
            }
            for s in steps
        ],
    }


# ─────────────────────────────────────────────
# GET /api/reviews/{review_run_id}/trace
# ─────────────────────────────────────────────
@router.get("/api/reviews/{review_run_id}/trace")
async def get_trace(
    review_run_id: str,
    db: AsyncSession = Depends(get_db_session),
    installation: Optional[Installation] = Depends(optional_installation),
):
    """Standalone reasoning trace endpoint for MCP tool."""
    run_id = _parse_uuid(review_run_id, "review_run_id")

    result = await db.execute(
        select(ReviewRun, PullRequest, Repository)
        .join(PullRequest, ReviewRun.pull_request_id == PullRequest.id)
        .join(Repository, PullRequest.repository_id == Repository.id)
        .where(ReviewRun.id == run_id)
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Review run not found")

    run, pr, repo_obj = row

    if installation and repo_obj.installation_id != installation.id:
        raise HTTPException(status_code=404, detail="Not found")

    steps_result = await db.execute(
        select(ReasoningStep)
        .where(ReasoningStep.review_run_id == run_id)
        .order_by(ReasoningStep.step_number)
    )
    steps = steps_result.scalars().all()

    return {
        "review_run_id": str(run.id),
        "pr_title": pr.title,
        "pr_number": pr.pr_number,
        "repo_full_name": repo_obj.full_name,
        "steps": [
            {
                "step_number": s.step_number,
                "step_type": s.step_type,
                "content": s.content,
                "tool_name": s.tool_name,
                "tool_input": s.tool_input,
                "tool_output_summary": s.tool_output_summary,
                "tokens_used": s.tokens_used,
                "duration_ms": s.duration_ms,
            }
            for s in steps
        ],
    }


# ─────────────────────────────────────────────
# GET /api/findings
# ─────────────────────────────────────────────
@router.get("/api/findings")
async def list_findings(
    severity: Optional[str] = None,
    category: Optional[str] = None,
    repo: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db_session),
    installation: Optional[Installation] = Depends(optional_installation),
):
    """List findings with optional filters. Scoped by installation if authed."""

    query = (
        select(
            Finding,
            PullRequest.pr_number,
            Repository.full_name.label("repo_full_name"),
        )
        .join(ReviewRun, Finding.review_run_id == ReviewRun.id)
        .join(PullRequest, ReviewRun.pull_request_id == PullRequest.id)
        .join(Repository, PullRequest.repository_id == Repository.id)
        .order_by(Finding.created_at.desc())
    )

    if installation:
        query = query.where(Repository.installation_id == installation.id)
    if severity:
        query = query.where(Finding.severity == severity)
    if category:
        query = query.where(Finding.category == category)
    if repo:
        query = query.where(Repository.full_name == repo)

    query = query.limit(limit).offset(offset)
    result = await db.execute(query)
    rows = result.all()

    return {
        "findings": [
            {
                "id": str(row.Finding.id),
                "severity": row.Finding.severity,
                "category": row.Finding.category,
                "title": row.Finding.title,
                "description": row.Finding.description,
                "suggestion": row.Finding.suggestion,
                "file_path": row.Finding.file_path,
                "line_number": row.Finding.line_number,
                "diff_position": row.Finding.diff_position,
                "was_posted": row.Finding.was_posted,
                "pr_number": row.pr_number,
                "repo_full_name": row.repo_full_name,
            }
            for row in rows
        ]
    }


# ─────────────────────────────────────────────
# GET /api/repos
# ─────────────────────────────────────────────
@router.get("/api/repos")
async def list_repos(
    db: AsyncSession = Depends(get_db_session),
    installation: Optional[Installation] = Depends(optional_installation),
):
    """List repositories with review stats."""

    query = select(Repository).order_by(Repository.last_reviewed_at.desc())
    if installation:
        query = query.where(Repository.installation_id == installation.id)

    result = await db.execute(query)
    repos = result.scalars().all()

    return {
        "repos": [
            {
                "id": str(r.id),
                "full_name": r.full_name,
                "owner": r.owner,
                "name": r.name,
                "is_private": r.is_private,
                "default_branch": r.default_branch,
                "total_reviews": r.total_reviews or 0,
                "total_findings": r.total_findings or 0,
                "review_enabled": r.review_enabled,
                "first_seen_at": r.first_seen_at.isoformat() if r.first_seen_at else None,
                "last_reviewed_at": r.last_reviewed_at.isoformat() if r.last_reviewed_at else None,
            }
            for r in repos
        ]
    }


# ─────────────────────────────────────────────
# GET /api/installations
# ─────────────────────────────────────────────
@router.get("/api/installations")
async def list_installations(
    db: AsyncSession = Depends(get_db_session),
):
    """List active installations (public endpoint for demo)."""

    result = await db.execute(
        select(Installation)
        .where(Installation.is_active.is_(True))
        .order_by(Installation.installed_at.desc())
    )
    installations = result.scalars().all()

    return {
        "installations": [
            {
                "id": str(i.id),
                "github_install_id": i.github_install_id,
                "account_login": i.account_login,
                "account_type": i.account_type,
                "account_avatar_url": i.account_avatar_url,
                "installed_at": i.installed_at.isoformat() if i.installed_at else None,
                "review_enabled": i.review_enabled,
                "review_categories": i.review_categories,
            }
            for i in installations
        ]
    }

# ─────────────────────────────────────────────
# GET /api/installations/by-github-id/{github_install_id}
# ─────────────────────────────────────────────
@router.get("/api/installations/by-github-id/{github_install_id}")
async def get_installation_by_github_id(
    github_install_id: str,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Look up an installation by its GitHub installation id, with its
    connected repos. Used by the post-install /welcome page: right after
    GitHub redirects back, the frontend only knows the GitHub install id
    (from the query string) and has no API key yet, so this has to be a
    public lookup keyed on that id rather than the authed /api/repos route.

    Accepts github_install_id as a string (not int) — GitHub install ids
    are stored as text on the Installation model, and asyncpg raises a
    DatatypeMismatchError (surfaced as a 500) if you compare a varchar
    column to a Python int.
    """
    result = await db.execute(
        select(Installation).where(
            Installation.github_install_id == github_install_id
        )
    )
    installation = result.scalar_one_or_none()
    if not installation:
        raise HTTPException(status_code=404, detail="Installation not found")

    repos_result = await db.execute(
        select(Repository).where(Repository.installation_id == installation.id)
    )
    repos = repos_result.scalars().all()

    return {
        "id": str(installation.id),
        "github_install_id": installation.github_install_id,
        "account_login": installation.account_login,
        "account_type": installation.account_type,
        "account_avatar_url": installation.account_avatar_url,
        "review_enabled": installation.review_enabled,
        "review_categories": installation.review_categories,
        "repositories": [
            {
                "id": str(r.id),
                "full_name": r.full_name,
                "is_private": r.is_private,
                "review_enabled": r.review_enabled,
            }
            for r in repos
        ],
    }

# ─────────────────────────────────────────────
# GET /api/connect  (requires auth)
# ─────────────────────────────────────────────
@router.get("/api/connect")
async def get_connect_info(
    request=None,
    db: AsyncSession = Depends(get_db_session),
    installation: Optional[Installation] = Depends(optional_installation),
):
    """Returns API key and MCP connection config for the settings page."""
    if not installation:
        raise HTTPException(status_code=401, detail="Authorization required")

    from app.services.api_key import ensure_api_key
    key = await ensure_api_key(db, installation)
    await db.commit()

    api_url = "https://your-railway-url.up.railway.app"

    return {
        "api_key": key,
        "api_url": api_url,
        "mcp_config": {
            "mcpServers": {
                "marginalia": {
                    "command": "python",
                    "args": ["mcp_server.py"],
                    "env": {
                        "MARGINALIA_API_KEY": key,
                        "MARGINALIA_API_URL": api_url,
                    },
                }
            }
        },
    }


# ─────────────────────────────────────────────
# POST /api/keys/rotate  (requires auth)
# ─────────────────────────────────────────────
@router.post("/api/keys/rotate")
async def rotate_key(
    db: AsyncSession = Depends(get_db_session),
    installation: Optional[Installation] = Depends(optional_installation),
):
    """Rotate the API key. Old key stops working immediately."""
    if not installation:
        raise HTTPException(status_code=401, detail="Authorization required")

    from app.services.api_key import rotate_api_key
    new_key = await rotate_api_key(db, installation)
    await db.commit()

    return {"api_key": new_key, "rotated": True}