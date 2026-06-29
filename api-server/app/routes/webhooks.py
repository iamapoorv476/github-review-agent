import json
import structlog
from datetime import datetime, timezone
from fastapi import APIRouter, Request, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_session
from app.middleware.webhook_auth import verify_github_webhook_signature
from app.utils.event_filter import filter_webhook_event, ReviewTrigger
from app.utils.idempotency import (
    generate_idempotency_key,
    is_duplicate,
    mark_as_processed
)
from app.utils.redis import get_redis
from app.services.installation_repository import upsert_installation
from app.services.repository_repository import upsert_repository
from app.services.pull_request_repository import upsert_pull_request
from app.services.review_run_repository import create_review_run

logger = structlog.get_logger()
router = APIRouter(tags=["webhooks"])

@router.post("/github")
async def github_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db_session)
) :
    """
    Entry point for all GitHub webhook events.

    Security: HMAC-SHA256 signature verified before any processing.
    Performance: Must respond in under 10 seconds — all LLM work
                 happens asynchronously in the worker.
    Reliability: Idempotency prevents duplicate jobs from retries.
    """

    # ----------------------------------------------------------------
    # Step 1 — Verify signature (security gate)
    # Nothing else runs if this fails — returns 401 immediately
    # ----------------------------------------------------------------

    raw_body = await verify_github_webhook_signature(request)

    # ----------------------------------------------------------------
    # Step 2 — Parse payload and extract event type
    # ----------------------------------------------------------------
    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError as e:
        logger.error("webhook_invalid_json", error=str(e))
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    
    event_type = request.headers.get("X-GitHub-Event", "")
    delivery_id = request.headers.get("X-GitHub-Delivery", "unknown")

    logger.info(
        "webhook_received",
        event_type=event_type,
        delivery_id=delivery_id,
        action=payload.get("action", "")
    )

    # ----------------------------------------------------------------
    # Step 3 — Filter events (only process what we care about)
    # ----------------------------------------------------------------

    filtered = filter_webhook_event(event_type, payload)

    if not filtered.should_process:
        logger.debug(
            "webhook_ignored",
            event_type=event_type,
            reason=filtered.reason
        )
        return {"status": "ignored", "reason": filtered.reason}
    
    # ----------------------------------------------------------------
    # Step 4 — Route to appropriate handler based on trigger type
    # ----------------------------------------------------------------
    if filtered.trigger == ReviewTrigger.INSTALLATION_CREATED:
        return await _handle_installation_created(payload, db)
    
    if filtered.trigger == ReviewTrigger.INSTALLATION_DELETED:
        return await _handle_installation_deleted(payload, db)
    
    if filtered.trigger in (
        ReviewTrigger.PR_OPENED,
        ReviewTrigger.PR_READY_FOR_REVIEW,
        ReviewTrigger.COMMENT_REREVIEW
    ):
        return await _handle_review_trigger(
            payload, filtered.trigger, db
        )
    
    return {"status": "ignored", "reason":"unhandled trigger type"}

async def _handle_installation_created(
    payload: dict,
    db: AsyncSession
) -> dict:
    """
    Handles new GitHub App installations.
    Creates the installation record in our database.
    """
    installation_data = payload.get("installation", {})
    account = installation_data.get("account", {})

    await upsert_installation(
        db=db,
        github_install_id=installation_data["id"],
        account_login=account.get("login", ""),
        account_type=account.get("type", "User"),
        account_avatar_url=account.get("avatar_url"),
        installed_at=datetime.now(timezone.utc)
    )

    logger.info(
        "installation_created",
        github_install_id=installation_data["id"],
        account=account.get("login")
    )

    return {"status": "ok", "action": "installation_created"}

async def _handle_installation_deleted(
    payload: dict,
    db: AsyncSession
) -> dict:
    """
    Handles GitHub App uninstallation.
    Soft-deletes the installation — preserves all review history.
    """
    from app.services.installation_repository import deactivate_installation

    installation_data = payload.get("installation", {})

    await deactivate_installation(
        db=db,
        github_install_id=installation_data["id"]
    )

    logger.info(
        "installation_deleted",
        github_install_id=installation_data["id"]
    )

    return {"status": "ok", "action": "installation_deleted"}

async def _handle_review_trigger(
        payload: dict,
        trigger: ReviewTrigger,
        db: AsyncSession
) -> dict:
    """
    Handles PR review triggers — the core webhook flow.

    Flow:
    1. Extract PR and repo data from payload
    2. Idempotency check
    3. Upsert installation, repo, PR in database
    4. Create review_run record
    5. Enqueue job
    6. Mark idempotency key
    """

    # ----------------------------------------------------------------
    # Extract data from payload
    # ----------------------------------------------------------------
    installation_data = payload.get("installation", {})
    repo_data = payload.get("repository", {})

    pr_data = payload.get("pull_request", {})

    if trigger == ReviewTrigger.COMMENT_REREVIEW:
        issue_data = payload.get("issue", {})
        pr_number = issue_data.get("number")

        head_sha = issue_data.get(
            "pull_request", {}
        ).get("head", {}).get("sha","unknown")
        title = issue_data.get("title", "")
        author_login= issue_data.get("user",{}).get("login","")
        triggered_by = payload.get(
            "comment", {}
        ).get("user", {}).get("login")
        base_branch = "unknown"
        head_branch ="unknown"
        github_pr_id = issue_data.get("id", 0)
        pr_opened_at = datetime.now(timezone.utc)
    else:
        pr_number = pr_data.get("number")
        head_sha = pr_data.get("head", {}).get("sha", "")
        title = pr_data.get("title", "")
        author_login = pr_data.get("user", {}).get("login", "")
        triggered_by = None
        base_branch = pr_data.get("base", {}).get("ref", "")
        head_branch = pr_data.get("head", {}).get("ref", "")
        github_pr_id = pr_data.get("id", 0)
        pr_opened_at_str = pr_data.get("created_at", "")
        try:
            pr_opened_at = datetime.fromisoformat(
                pr_opened_at_str.replace("Z", "+00:00")
            )
        except (ValueError, AttributeError):
            pr_opened_at = datetime.now(timezone.utc)

    installation_id_github = installation_data.get("id")

    if not installation_id_github or not pr_number:
        logger.error(
            "webhook_missing_required_fields",
            installation_id=installation_id_github,
            pr_number=pr_number
        )
        raise HTTPException(
            status_code=400,
            detail="Missing required fields in payload"
        )
    
    # ----------------------------------------------------------------
    # Idempotency check — before any database writes
    # ----------------------------------------------------------------
    idempotency_key = generate_idempotency_key(
        installation_id=installation_id_github,
        repo_id=repo_data.get("id", 0),
        pr_number=pr_number,
        head_sha=head_sha
    )

    redis = await get_redis()

    try:
        duplicate = await is_duplicate(redis, idempotency_key)
        if duplicate:
            logger.info(
                "webhook_duplicate_ignored",
                idempotency_key=idempotency_key
            )
            return {"status": "ignored", "reason": "duplicate event"}
    except Exception as e:
        # Redis is down — fail closed
        logger.error(
            "idempotency_check_failed_failing_closed",
            error=str(e)
        )
        raise HTTPException(
            status_code=503,
            detail="Service temporarily unavailable"
        )
    # ----------------------------------------------------------------
    # Database operations — upsert installation, repo, PR
    # ----------------------------------------------------------------
    account = installation_data.get("account", {})

    installation = await upsert_installation(
        db=db,
        github_install_id=installation_id_github,
        account_login=account.get("login", ""),
        account_type=account.get("type", "User"),
        account_avatar_url=account.get("avatar_url"),
        installed_at=datetime.now(timezone.utc)
    )

    repository = await upsert_repository(
        db=db,
        installation_id=installation.id,
        github_repo_id=repo_data.get("id", 0),
        owner=repo_data.get("owner", {}).get("login", ""),
        name=repo_data.get("name", ""),
        full_name=repo_data.get("full_name", ""),
        is_private=repo_data.get("private", False),
        default_branch=repo_data.get("default_branch", "main")
    )

    pull_request = await upsert_pull_request(
        db=db,
        repository_id=repository.id,
        github_pr_id=github_pr_id,
        pr_number=pr_number,
        title=title,
        author_login=author_login,
        base_branch=base_branch,
        head_branch=head_branch,
        head_sha=head_sha,
        pr_opened_at=pr_opened_at
    )

    # ----------------------------------------------------------------
    # Create review run record
    # ----------------------------------------------------------------
    review_run = await create_review_run(
        db=db,
        pull_request_id=pull_request.id,
        trigger=trigger.value,
        idempotency_key=idempotency_key,
        triggered_by=triggered_by
    )
    job_payload = {
        "review_run_id": str(review_run.id),
        "installation_github_id": installation_id_github,
        "repo_full_name": repo_data.get("full_name", ""),
        "pr_number": pr_number,
        "head_sha": head_sha,
        "trigger": trigger.value
    }

    logger.info(
        "review_job_would_enqueue",
        **job_payload
    )

    try:
        await mark_as_processed(redis, idempotency_key)
    except Exception as e:
        logger.error(
            "idempotency_mark_failed",
            error=str(e),
            idempotency_key=idempotency_key
        )
        # Don't fail the request — job was already enqueued successfully

    logger.info(
        "webhook_processed_successfully",
        review_run_id=str(review_run.id),
        trigger=trigger.value,
        pr_number=pr_number
    )

    return {
        "status": "ok",
        "review_run_id": str(review_run.id),
        "trigger": trigger.value
    }



