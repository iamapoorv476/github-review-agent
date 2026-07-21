import structlog
from redis.asyncio import Redis

logger = structlog.get_logger()

IDEMPOTENCY_TTL_SECONDS = 86400

def generate_idempotency_key(
        installation_id: int,
        repo_id: int,
        pr_number: int,
        head_sha: str
) -> str:
    """
    Generates a deterministic idempotency key for a review job.

    Key format: gra:idem:{installation_id}:{repo_id}:{pr_number}:{head_sha}
    The head_sha is critical — a new commit to the PR changes the SHA,
    which legitimately triggers a new review. Same SHA = same event = duplicate.
    """
    return f"gra:idem:{installation_id}:{repo_id}:{pr_number}:{head_sha}"

async def is_duplicate(redis: Redis, key: str) -> bool:
    """
    Checks if this event has already been processed.
    Returns True if duplicate, False if new.
    """
    try:
        exists= await redis.exists(key)
        return bool(exists)
    except Exception as e:
        logger.error(
            "idempotency_check_failed",
            key=key,
            error=str(e)
        )
        # Fail closed — if Redis is down, treat as potential duplicate
        # GitHub will retry and we'll process when Redis recovers
        raise

async def mark_as_processed(redis: Redis, key: str) -> None:
    """
    Marks an event as processed AFTER the job is successfully enqueued.
    TTL of 24 hours — after that, the same event could re-trigger.

    IMPORTANT: This must be called AFTER successful job enqueue,
    never before. If enqueue fails, the key must not be set so
    GitHub's retry can try again.
    """
    try:
        await redis.set(key, "1", ex=IDEMPOTENCY_TTL_SECONDS)
        logger.debug("idempotency_key_set", key=key, ttl=IDEMPOTENCY_TTL_SECONDS)
    except Exception as e:
        logger.error(
            "idempotency_mark_failed",
            key=key,
            error=str(e)
        )
        raise