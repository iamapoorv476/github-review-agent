import json
import structlog
from bullmq import Queue
from app.config import get_settings

logger = structlog.get_logger()

REVIEW_QUEUE_NAME = "review-jobs"

_queue: Queue | None = None


def _get_redis_opts(redis_url: str) -> dict:
    """Parses redis URL into host/port dict for BullMQ."""
    stripped = redis_url.replace("redis://", "")
    parts = stripped.split(":")
    return {
        "host": parts[0],
        "port": int(parts[1]) if len(parts) > 1 else 6379
    }


async def get_queue() -> Queue:
    global _queue
    if _queue is None:
        settings = get_settings()
        redis_opts = _get_redis_opts(settings.redis_url)

        _queue = Queue(
            REVIEW_QUEUE_NAME,
            {
                "connection": redis_opts
            }
        )
        logger.info(
            "bullmq_queue_created",
            queue_name=REVIEW_QUEUE_NAME
        )
    return _queue


async def enqueue_review_job(job_payload: dict) -> str:
    queue = await get_queue()

    job = await queue.add(
        "review-pr",
        job_payload,
        {
            "attempts": 3,
            "backoff": {
                "type": "exponential",
                "delay": 2000
            },
            "removeOnComplete": {"count": 100},
            "removeOnFail": False
        }
    )

    logger.info(
        "review_job_enqueued",
        job_id=job.id,
        review_run_id=job_payload.get("review_run_id"),
        pr_number=job_payload.get("pr_number"),
        repo=job_payload.get("repo_full_name")
    )

    return job.id


async def close_queue() -> None:
    global _queue
    if _queue is not None:
        await _queue.close()
        _queue = None
        logger.info("bullmq_queue_closed")