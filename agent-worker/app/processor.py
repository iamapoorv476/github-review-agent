import structlog
from datetime import datetime, timezone
from app.config import get_settings
from app.services.review_run_repository import update_review_run_status, get_review_run

logger = structlog.get_logger()

async def process_review_job(job_data: dict) -> None:
    """
    Full review pipeline:
    1. Get valid GitHub token (rotate if needed)
    2. Fetch PR metadata and diff
    3. Build diff position maps
    4. Run LangGraph agent
    5. Post review to GitHub
    6. Store findings in database
    """

    from app.database import get_session_factory
    from app.services.github_auth import get_valid_token
    from app.services.github_client import GitHubClient
    from app.utils.diff_mapper import build_position_maps
    from app.agent.reviewer import run_review_agent

    settings = get_settings()

    review_run_id = job_data["review_run_id"]
    installation_github_id = job_data["installation_github_id"]
    repo_full_name = job_data["repo_full_name"]
    pr_number = job_data["pr_number"]
    head_sha = job_data["head_sha"]

    logger.info(
        "processor_started",
        review_run_id=review_run_id,
        repo=repo_full_name,
        pr_number=pr_number
    )

    factory = get_session_factory()

    async with factory() as db:
        try:
            # Step 1 — Update status to processing
            
            await update_review_run_status(
                db, review_run_id, "processing"
            )
            await db.commit()

            # Step 2 — Get valid GitHub token
            logger.info("step_getting_github_token")
            token = await get_valid_token(
                installation_github_id, db
            )
            await db.commit()

            # Step 3 - Initialize GitHub client
            github_client = GitHubClient(
                token=token,
                repo_full_name=repo_full_name
            )

            # Step 4 - Fetch PR metadata
            logger.info("step_fetching_pr_metadata")
            pr_metadata = await github_client.get_pr_metadata(pr_number)

            logger.info("step_fetching_pr_files")
            pr_files = await github_client.get_pr_files(pr_number)
            github_client._cached_files = pr_files
            github_client._current_pr_number = pr_number

            position_maps = build_position_maps(pr_files)
            logger.info(
                "position_maps_built",
                files_with_diffs=len(position_maps)
            )

            # Step 6 — Run agent (mock or real based on config)
            logger.info(
                "step_running_agent",
                mock=settings.mock_llm
            )
            findings= await run_review_agent(
                github_client=github_client,
                position_maps=position_maps,
                head_sha=head_sha,
                pr_metadata=pr_metadata,
                mock=settings.mock_llm
            )

            logger.info(
                "agent_completed",
                findings_count=len(findings)
            )

            # Step 7 — Build review summary
            critical = [f for f in findings if f["severity"] == "critical"]
            high = [f for f in findings if f["severity"] == "high"]
            medium = [f for f in findings if f["severity"] == "medium"]
            low = [f for f in findings if f["severity"] == "low"]

            summary = _build_review_summary(
                findings, critical, high, medium, low
            )

            github_review_id = None
            if not settings.mock_llm and findings:
                logger.info("step_posting_to_github")
                comments = [
                    {
                        "path": f["file_path"],
                        "position":f["diff_position"],
                        "body": _format_comment(f)

                    }
                    for f in findings
                    if f.get("diff_position") is not None
                ]

                github_review_id = await github_client.post_review_with_comments(
                    pr_number=pr_number,
                    commit_sha=head_sha,
                    summary=summary,
                    comments=comments
                )

            logger.info("step_storing_findings")
            await _store_findings(
                db, review_run_id, findings
            )


            # Update review run as completed
            from app.models.review_run import ReviewRun
            from sqlalchemy import select
            import uuid

            result = await db.execute(
                select(ReviewRun).where(
                    ReviewRun.id == uuid.UUID(review_run_id)
                )
            )
            review_run = result.scalar_one()
            review_run.status = "completed"
            review_run.completed_at = datetime.now(timezone.utc)
            review_run.findings_count = len(findings)
            review_run.critical_count = len(critical)
            review_run.high_count = len(high)
            review_run.medium_count = len(medium)
            review_run.low_count = len(low)
            if github_review_id:
                review_run.github_review_id = github_review_id

            await db.commit()

            logger.info(
                "processor_finished",
                review_run_id=review_run_id,
                findings=len(findings),
                critical=len(critical),
                high=len(high)
            )
        except Exception as e:
            logger.error(
                "processor_failed",
                review_run_id=review_run_id,
                error=str(e),
                exc_info =True
            )
            try:
                await update_review_run_status(
                    db, review_run_id, "failed",
                    error_message=str(e)
                )
                await db.commit()
            except Exception as inner_e:
                logger.error(
                    "failed_to_update_status",
                    error=str(inner_e)
                    
                )
            raise


def _build_review_summary(
        findings, critical, high, medium, low
) -> str:
    if not findings:
        return (
            "## PR Review Complete\n\n"
            "No significant issues found. "
            "The code looks good to merge."
        )
    
    lines = [
        "## PR Review Summary\n",
        f"Found **{len(findings)} issue(s)**:\n",
    ]

    if critical:
        lines.append(f"- 🔴 **{len(critical)} Critical**")
    if high:
        lines.append(f"- 🟠 **{len(high)} High**")
    if medium:
        lines.append(f"- 🟡 {len(medium)} Medium")
    if low:
        lines.append(f"- 🔵 {len(low)} Low")

    if critical or high:
        lines.append(
            "\n⚠️ **This PR has critical or high severity issues "
            "that should be addressed before merging.**"
        )

    lines.append("\n*Review powered by GitHub Review Agent*")
    return "\n".join(lines)

def _format_comment(finding: dict) -> str:
    severity_emoji = {
        "critical": "🔴",
        "high": "🟠",
        "medium": "🟡",
        "low": "🔵"
    }
    emoji = severity_emoji.get(finding["severity"], "⚪")

    return (
        f"{emoji} **[{finding['severity'].upper()}] "
        f"{finding['title']}**\n\n"
        f"{finding['description']}\n\n"
        f"**Suggestion:** {finding['suggestion']}"
    )

async def _store_findings(
        db,
        review_run_id: str,
        findings: list[dict]
) -> None:
    """Stores all findings in the database."""
    import uuid
    from app.models.finding import Finding

    for f in findings:
        finding = Finding(
            review_run_id=uuid.UUID(review_run_id),
            file_path=f["file_path"],
            line_number=f.get("line_number"),
            diff_position=f.get("diff_position"),
            category=f["category"],
            severity=f["severity"],
            title=f["title"],
            description=f["description"],
            suggestion=f.get("suggestion"),
            was_posted=f.get("diff_position") is not None
        )
        db.add(finding)
    
    await db.flush()
    logger.info(
        "findings_stored",
        count=len(findings),
        review_run_id=review_run_id
    )
            

            