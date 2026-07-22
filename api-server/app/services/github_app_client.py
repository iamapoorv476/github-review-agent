import structlog
import httpx
import time
import jwt
from app.config import get_settings

logger = structlog.get_logger()
GITHUB_API_BASE = "https://api.github.com"


def _clean_private_key(key: str) -> str:
    if "\\n" in key:
        key = key.replace("\\n", "\n")
    if "\n" not in key:
        key = key.replace(
            "-----BEGIN RSA PRIVATE KEY-----", ""
        ).replace(
            "-----END RSA PRIVATE KEY-----", ""
        ).replace(
            "-----BEGIN PRIVATE KEY-----", ""
        ).replace(
            "-----END PRIVATE KEY-----", ""
        ).strip()
        chunks = [key[i:i+64] for i in range(0, len(key), 64)]
        key = (
            "-----BEGIN RSA PRIVATE KEY-----\n" +
            "\n".join(chunks) +
            "\n-----END RSA PRIVATE KEY-----\n"
        )
    return key.strip()


def generate_app_jwt() -> str:
    settings = get_settings()
    now = int(time.time())
    payload = {
        "iat": now - 60,
        "exp": now + 540,
        "iss": int(settings.github_app_id)
    }
    private_key = _clean_private_key(settings.github_private_key)
    return jwt.encode(payload, private_key, algorithm="RS256")


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
