import time
import structlog
import httpx
import jwt
from datetime import datetime, timezone, timedelta
from app.config import get_settings

logger = structlog.get_logger()

GITHUB_API_BASE = "https://api.github.com"


def _clean_private_key(key: str) -> str:
    """
    Ensures the private key has proper PEM formatting.
    Handles cases where newlines are stored as literal \n strings.
    """
    # If key contains literal \n strings, replace with real newlines
    if "\\n" in key:
        key = key.replace("\\n", "\n")

    # If key is all on one line (no newlines), reformat it
    if "\n" not in key:
        # Extract the base64 content between headers
        key = key.replace(
            "-----BEGIN RSA PRIVATE KEY-----", ""
        ).replace(
            "-----END RSA PRIVATE KEY-----", ""
        ).replace(
            "-----BEGIN PRIVATE KEY-----", ""
        ).replace(
            "-----END PRIVATE KEY-----", ""
        ).strip()

        # Reformat with proper line breaks every 64 chars
        chunks = [key[i:i+64] for i in range(0, len(key), 64)]
        key = (
            "-----BEGIN RSA PRIVATE KEY-----\n" +
            "\n".join(chunks) +
            "\n-----END RSA PRIVATE KEY-----\n"
        )

    return key.strip()


def generate_jwt() -> str:
    settings = get_settings()

    now = int(time.time())
    payload = {
        "iat": now - 60,
        "exp": now + 540,
        "iss": int(settings.github_app_id)
    }

    private_key = _clean_private_key(settings.github_private_key)

    token = jwt.encode(
        payload,
        private_key,
        algorithm="RS256"
    )

    logger.debug("github_jwt_generated", app_id=settings.github_app_id)
    return token


async def get_installation_token(
    installation_github_id: int
) -> tuple[str, datetime]:
    jwt_token = generate_jwt()

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

        if response.status_code != 201:
            logger.error(
                "github_token_request_failed",
                status=response.status_code,
                body=response.text[:200]
            )
            raise Exception(
                f"Failed to get installation token: "
                f"{response.status_code} {response.text[:200]}"
            )

        data = response.json()
        token = data["token"]
        expires_at = datetime.fromisoformat(
            data["expires_at"].replace("Z", "+00:00")
        )

        logger.info(
            "github_installation_token_obtained",
            installation_id=installation_github_id,
            expires_at=expires_at.isoformat()
        )

        return token, expires_at


def token_needs_rotation(expires_at: datetime) -> bool:
    buffer = timedelta(minutes=5)
    now = datetime.now(timezone.utc)
    return (expires_at - now) < buffer


async def get_valid_token(
    installation_github_id: int,
    db
) -> str:
    from sqlalchemy import select
    from app.models.installation import Installation
    from app.utils.encryption import decrypt_token, encrypt_token

    result = await db.execute(
        select(Installation).where(
            Installation.github_install_id == installation_github_id
        )
    )
    installation = result.scalar_one_or_none()

    if not installation:
        raise Exception(
            f"Installation {installation_github_id} not found in database"
        )

    if (
        installation.access_token
        and installation.access_token_expires_at
        and not token_needs_rotation(installation.access_token_expires_at)
    ):
        logger.debug(
            "github_token_still_valid",
            installation_id=installation_github_id,
            expires_at=installation.access_token_expires_at.isoformat()
        )
        return decrypt_token(installation.access_token)

    logger.info(
        "github_token_rotating",
        installation_id=installation_github_id
    )

    token, expires_at = await get_installation_token(installation_github_id)

    installation.access_token = encrypt_token(token)
    installation.access_token_expires_at = expires_at
    await db.flush()

    logger.info(
        "github_token_stored",
        installation_id=installation_github_id,
        expires_at=expires_at.isoformat()
    )

    return token
