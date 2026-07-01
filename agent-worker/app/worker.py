import asyncio
import structlog
from bullmq import Worker

from app.config import get_settings
from app.processor import process_review_job

logger = structlog.get_logger()

REVIEW_QUEUE_NAME = "review-jobs"


def setup_logging():
    import logging
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.format_exc_info,
            structlog.dev.ConsoleRenderer()
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.DEBUG
        ),
        logger_factory=structlog.PrintLoggerFactory()
    )


async def process_job(job, job_token):
    logger.info(
        "job_picked_up",
        job_id=job.id,
        review_run_id=job.data.get("review_run_id"),
        pr_number=job.data.get("pr_number"),
        repo=job.data.get("repo_full_name")
    )

    try:
        await process_review_job(job.data)
        logger.info(
            "job_completed",
            job_id=job.id,
            review_run_id=job.data.get("review_run_id")
        )
    except Exception as e:
        logger.error(
            "job_failed",
            job_id=job.id,
            review_run_id=job.data.get("review_run_id"),
            error=str(e)
        )
        raise


async def main():
    setup_logging()
    settings = get_settings()

    redis_host = settings.redis_url.replace("redis://", "").split(":")[0]
    redis_port = int(settings.redis_url.replace("redis://", "").split(":")[1])

    logger.info(
        "worker_starting",
        queue=REVIEW_QUEUE_NAME,
        concurrency=settings.worker_concurrency,
        mock_llm=settings.mock_llm
    )

    worker = Worker(
        REVIEW_QUEUE_NAME,
        process_job,
        {
            "connection": {
                "host": redis_host,
                "port": redis_port
            },
            "concurrency": settings.worker_concurrency
        }
    )

    logger.info("worker_ready", queue=REVIEW_QUEUE_NAME)

    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("worker_stopping")
        await worker.close()


if __name__ == "__main__":
    asyncio.run(main())