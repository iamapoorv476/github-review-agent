import asyncio
import structlog
from datetime import datetime, timezone

logger = structlog.get_logger()


async def process_review_job(job_data: dict) -> None:
    """
    Processes a review job from the queue.

    Current mode: MOCK — simulates agent behavior without LLM calls.
    Phase 4: Replace mock with real LangGraph agent.
    """
    review_run_id = job_data.get("review_run_id")
    repo_full_name = job_data.get("repo_full_name")
    pr_number = job_data.get("pr_number")
    head_sha = job_data.get("head_sha")
    installation_github_id = job_data.get("installation_github_id")

    logger.info(
        "processor_started",
        review_run_id=review_run_id,
        repo=repo_full_name,
        pr_number=pr_number,
        head_sha=head_sha[:8] if head_sha else None
    )

    # Simulate the steps the real agent will take
    steps = [
        ("fetching_pr_metadata", 0.5),
        ("fetching_pr_diff", 1.0),
        ("triage_phase_analyzing_files", 1.0),
        ("deep_review_security_check", 1.5),
        ("deep_review_performance_check", 1.0),
        ("deep_review_quality_check", 0.8),
        ("mapping_findings_to_diff_positions", 0.3),
        ("posting_review_to_github", 0.5),
    ]

    for step_name, delay in steps:
        logger.info(
            f"mock_step_{step_name}",
            review_run_id=review_run_id
        )
        await asyncio.sleep(delay)

    # Mock findings that the real agent would produce
    mock_findings = [
        {
            "file_path": "test.py",
            "line_number": 4,
            "category": "security",
            "severity": "critical",
            "title": "Hardcoded API key detected",
            "description": (
                "API_KEY is hardcoded in source code. "
                "This will be exposed if the repository is public "
                "or if git history is accessed."
            ),
            "suggestion": (
                "Use environment variables: "
                "os.environ.get('API_KEY')"
            )
        },
        {
            "file_path": "test.py",
            "line_number": 7,
            "category": "security",
            "severity": "high",
            "title": "SQL injection vulnerability",
            "description": (
                "User input is directly interpolated into SQL query "
                "via f-string. This allows SQL injection attacks."
            ),
            "suggestion": (
                "Use parameterized queries: "
                "cursor.execute('SELECT * FROM users WHERE id = %s', "
                "[user_id])"
            )
        }
    ]

    logger.info(
        "mock_review_complete",
        review_run_id=review_run_id,
        findings_count=len(mock_findings),
        mock_findings=mock_findings
    )

    logger.info(
        "processor_finished",
        review_run_id=review_run_id,
        duration_simulated="6.6 seconds",
        findings=len(mock_findings)
    )