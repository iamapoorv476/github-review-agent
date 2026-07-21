import json
import structlog
from app.utils.queue import enqueue_review_job
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
from app.services.installation_repository import (
    upsert_installation,
    get_installation_by_github_id,
)
from app.services.repository_repository import (
    upsert_repository,
    register_repositories_from_install,
    disable_repositories_by_github_id,
)
from app.services.pull_request_repository import upsert_pull_request
from app.services.review_run_repository import (
    create_review_run,
    count_reviews_today_for_installation,
)
from app.config import get_settings

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

    if filtered.trigger == ReviewTrigger.INSTALLATION_REPOS_CHANGED:
        return await _handle_installation_repos_changed(payload, db)
    
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

    installation = await upsert_installation(
        db=db,
        github_install_id=installation_data["id"],
        account_login=account.get("login", ""),
        account_type=account.get("type", "User"),
        account_avatar_url=account.get("avatar_url"),
        installed_at=datetime.now(timezone.utc)
    )

    # Register the repos selected during install so /welcome shows the true
    # selection immediately, instead of waiting for the first PR (lazy path).
    repositories = payload.get("repositories", [])
    repo_count = await register_repositories_from_install(
        db=db,
        installation_id=installation.id,
        repositories=repositories,
    )

    logger.info(
        "installation_created",
        github_install_id=installation_data["id"],
        account=account.get("login"),
        repo_count=repo_count
    )

    return {
        "status": "ok",
        "action": "installation_created",
        "repositories_registered": repo_count
    }

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

async def _handle_installation_repos_changed(
    payload: dict,
    db: AsyncSession
) -> dict:
    """
    Handles repos being added to / removed from an existing installation
    (the `installation_repositories` event). Keeps the dashboard and /welcome
    in sync with the repo selection on GitHub without waiting for a PR.
    """
    installation_data = payload.get("installation", {})
    github_install_id = installation_data.get("id")

    # The installation must already exist (created on install). If a race
    # means it doesn't, upsert a minimal record from this payload's account.
    installation = await get_installation_by_github_id(db, github_install_id)
    if installation is None:
        account = installation_data.get("account", {})
        installation = await upsert_installation(
            db=db,
            github_install_id=github_install_id,
            account_login=account.get("login", ""),
            account_type=account.get("type", "User"),
            account_avatar_url=account.get("avatar_url"),
            installed_at=datetime.now(timezone.utc)
        )

    added = await register_repositories_from_install(
        db=db,
        installation_id=installation.id,
        repositories=payload.get("repositories_added", []),
    )
    removed = await disable_repositories_by_github_id(
        db=db,
        github_repo_ids=[
            r["id"] for r in payload.get("repositories_removed", [])
        ],
    )

    logger.info(
        "installation_repos_changed",
        github_install_id=github_install_id,
        added=added,
        removed=removed
    )

    return {
        "status": "ok",
        "action": "installation_repos_changed",
        "added": added,
        "removed": removed
    }

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
        from app.services.github_app_client import fetch_pr_current_state


        issue_data = payload.get("issue", {})
        pr_number = issue_data.get("number")
        triggered_by = payload.get(
            "comment", {}
        ).get("user", {}).get("login")
        repo_full_name = repo_data.get("full_name", "")
        installation_github_id_for_fetch = installation_data.get("id")

        try:
            pr_state = await fetch_pr_current_state(
                installation_github_id=installation_github_id_for_fetch,
                repo_full_name=repo_full_name,
                pr_number=pr_number
            )
            head_sha = pr_state["head_sha"]
            title = pr_state["title"]
            author_login = pr_state["author_login"]
            base_branch = pr_state["base_branch"]
            head_branch = pr_state["head_branch"]
            github_pr_id = pr_state["github_pr_id"]
            try:
                pr_opened_at = datetime.fromisoformat(
                    pr_state["pr_opened_at"].replace("Z", "+00:00")
                )
            except (ValueError, AttributeError):
                pr_opened_at = datetime.now(timezone.utc)

            logger.info(
                "rereview_pr_state_fetched",
                pr_number=pr_number,
                head_sha=head_sha[:8]
            )
        except Exception as e:
            logger.error(
                "rereview_pr_state_fetch_failed",
                pr_number=pr_number,
                error=str(e)
            )
            raise HTTPException(
                status_code=503,
                detail="Could not fetch PR state for re-review"
            )
    
        
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

    # ----------------------------------------------------------------
    # Daily cost cap — every review is real LLM spend. Enforced per
    # installation per UTC day, before anything is enqueued.
    # ----------------------------------------------------------------
    settings = get_settings()
    cap = settings.max_reviews_per_installation_per_day
    if cap > 0:
        reviews_today = await count_reviews_today_for_installation(
            db=db, installation_id=installation.id
        )
        if reviews_today >= cap:
            logger.warning(
                "review_cap_reached",
                installation_id=str(installation.id),
                account=account.get("login"),
                reviews_today=reviews_today,
                cap=cap
            )
            # Tell the PR author once per PR per day — not on every push.
            notice_key = (
                f"gra:capnotice:{installation_id_github}:"
                f"{repo_data.get('id', 0)}:{pr_number}:"
                f"{datetime.now(timezone.utc):%Y%m%d}"
            )
            try:
                first_notice = await redis.set(notice_key, "1", ex=86400, nx=True)
            except Exception:
                first_notice = False  # Redis hiccup — skip the comment, keep the 200
            if first_notice and not settings.mock_github:
                from app.services.github_app_client import post_issue_comment
                await post_issue_comment(
                    installation_github_id=installation_id_github,
                    repo_full_name=repo_data.get("full_name", ""),
                    pr_number=pr_number,
                    body=(
                        f"Marginalia has reached its daily review limit for "
                        f"this account ({cap} reviews). The limit resets at "
                        f"midnight UTC — comment `@marginalia review` then to "
                        f"review this PR."
                    ),
                )
            # Deliberately NOT marked in idempotency: the same head_sha can
            # be reviewed after the cap resets via @marginalia review.
            return {
                "status": "ignored",
                "reason": f"daily review cap reached ({reviews_today}/{cap})"
            }

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
        "repo_id": str(repository.id),
        "head_sha": head_sha,
        "trigger": trigger.value
    }
    bullmq_job_id = await enqueue_review_job(job_payload)
    review_run.bullmq_job_id = bullmq_job_id



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