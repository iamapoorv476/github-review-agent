"""
Per-installation API keys — issued at install, used by the MCP server
(and any external client) to read that installation's data.

Design:
  - plaintext format: gra_<43 url-safe chars> (~256 bits of entropy)
  - api_key_hash     = sha256 hex → unique-indexed, O(1) auth lookup
  - api_key_encrypted = Fernet    → re-displayable on the connect page

Trade-off, stated honestly: storing a decryptable copy is weaker than
hash-only, but the product needs to show the key on the dashboard and
the dashboard has no login yet. Hash-only + "shown once" is the upgrade
path once session auth exists.
"""
import hashlib
import secrets

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.installation import Installation
from app.utils.encryption import encrypt_token, decrypt_token

logger = structlog.get_logger()

KEY_PREFIX = "gra_"


def generate_api_key() -> str:
    return KEY_PREFIX + secrets.token_urlsafe(32)


def hash_api_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


async def ensure_api_key(db: AsyncSession, installation: Installation) -> str:
    """
    Return the installation's plaintext key, creating one if absent.
    Idempotent — re-installs and repeated /welcome loads keep the same key.
    """
    if installation.api_key_encrypted:
        return decrypt_token(installation.api_key_encrypted)

    key = generate_api_key()
    installation.api_key_hash = hash_api_key(key)
    installation.api_key_encrypted = encrypt_token(key)
    await db.flush()
    logger.info(
        "api_key_issued",
        installation_id=str(installation.id),
        account=installation.account_login,
    )
    return key


async def rotate_api_key(db: AsyncSession, installation: Installation) -> str:
    """Replace the key. The old one stops working immediately."""
    key = generate_api_key()
    installation.api_key_hash = hash_api_key(key)
    installation.api_key_encrypted = encrypt_token(key)
    await db.flush()
    logger.info(
        "api_key_rotated",
        installation_id=str(installation.id),
        account=installation.account_login,
    )
    return key


async def resolve_api_key(db: AsyncSession, key: str) -> Installation | None:
    """Plaintext key → active Installation, or None."""
    if not key or not key.startswith(KEY_PREFIX):
        return None
    result = await db.execute(
        select(Installation).where(
            Installation.api_key_hash == hash_api_key(key),
            Installation.is_active.is_(True),
        )
    )
    return result.scalar_one_or_none()