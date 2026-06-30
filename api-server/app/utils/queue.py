import json
import structlog
from bullmq import Queue
from app.config import get_settings

logger = structlog.get_logger()

REVIEW_QUEUE_NAME = "review-jobs"

_queue: Queue | None = None

async def get_queue() -> Queue:
    """
    Returns the shared BullMQ queue instance.
    Creates it on first call.
    """
    global _queue
    if _queue is None:
        settings= get_settings()
        _queue = Queue(
            REVIEW_QUEUE_NAME,
            connection={
                "host":_parse_redis_host(settings.redis_url),
                "port":_parse_redis_port(settings.redis_url),
            }
        )
        logger.info(
            "bullmq_queue_created",
            queue_name=REVIEW_QUEUE_NAME
        )
        return _queue
    
def _parse_redis_host(redis_url: str) -> str:
    """Extracts host from redis://host:port URL."""
    return redis_url.replace("redis://","").split(":")[0]

def _parse_redis_port(redis_url: str) -> int:
    """Extracts port from redis://host:port URL."""
    try:
        return int(redis_url.replace("redis://", "").split(":")[1])
    except(IndexError, ValueError):
        return 6379
    
async def enqueue_review_job(job_payload: dict) -> str:
    """
    Enqueues a review job to BullMQ.

    Returns the BullMQ job ID for tracking.

    Job options:
    - attempts: 3 retries before dead letter
    - backoff: exponential (2s, 4s, 8s between retries)
    - removeOnComplete: keep last 100 completed jobs for Bull Board
    - removeOnFail: keep all failed jobs for debugging
    """
    queue = await get_queue()

    job = await queue.add(
        "review-pr",
        job_payload,
        opts={
            "attempts": 3,
            "backoff":{
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
    """
    Closes the queue connection cleanly on shutdown.
    """

    global _queue
    if _queue is not None:
        await _queue.close()
        _queue = None
        logger.info("bullmq_queue_closed")
