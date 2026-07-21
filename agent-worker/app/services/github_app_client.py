import structlog
import httpx
import time
import jwt
from app.config import get_settings

logger = structlog.get_logger()
GITHUB_API_BASE = "https://api.github.com"


def generate_app_jwt() -> str:
    settings = get_settings()
    now = int(time.time())
    payload = {
        "iat": now - 60,
        "exp": now + 540,
        "iss": int(settings.github_app_id)
    }
    return jwt.encode(
        payload,
        settings.github_private_key,
        algorithm="RS256"
    )


async def get_installation_access_token(
    installation_github_id: int
) -> str:
    jwt_token = generate_app_jwt()

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{GITHUB_API_BASE}/app/installations/"
            f"{installation_github_id}/access_tokens",
            headers={
                "Authorization": f"Bearer {jwt_token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28"
            }
        )
        response.raise_for_status()
        return response.json()["token"]


async def fetch_pr_current_state(
    installation_github_id: int,
    repo_full_name: str,
    pr_number: int
) -> dict:
    try:
        token = await get_installation_access_token(
            installation_github_id
        )

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{GITHUB_API_BASE}/repos/{repo_full_name}"
                f"/pulls/{pr_number}",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28"
                },
                timeout=10.0
            )
            response.raise_for_status()
            data = response.json()

        return {
            "head_sha": data["head"]["sha"],
            "title": data["title"],
            "author_login": data["user"]["login"],
            "base_branch": data["base"]["ref"],
            "head_branch": data["head"]["ref"],
            "github_pr_id": data["id"],
            "pr_opened_at": data["created_at"]
        }

    except Exception as e:
        logger.error(
            "fetch_pr_state_failed",
            repo=repo_full_name,
            pr_number=pr_number,
            error=str(e)
        )
        raise


async def post_issue_comment(
    installation_github_id: int,
    repo_full_name: str,
    pr_number: int,
    body: str,
) -> None:
    """
    Post a plain issue comment on a PR (PRs are issues for comment purposes).
    Used for out-of-band notices like the daily review cap. Failures are
    logged but never raised — a notice must not break webhook handling.
    """
    try:
        token = await get_installation_access_token(installation_github_id)

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{GITHUB_API_BASE}/repos/{repo_full_name}"
                f"/issues/{pr_number}/comments",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28"
                },
                json={"body": body},
                timeout=10.0
            )
            response.raise_for_status()

        logger.info(
            "issue_comment_posted",
            repo=repo_full_name,
            pr_number=pr_number
        )
    except Exception as e:
        logger.error(
            "issue_comment_post_failed",
            repo=repo_full_name,
            pr_number=pr_number,
            error=str(e)
        )