"""
Optional API-key auth for the read API.

One code path, two behaviors:
  - No Authorization header  → None → endpoints serve global (demo) data,
    exactly as before. The public dashboard keeps working unchanged.
  - "Authorization: Bearer gra_..." → resolves to an Installation and every
    query is scoped to that installation's data. Invalid keys are rejected
    (401) rather than silently downgraded to demo mode — a client that
    *tried* to authenticate should never receive someone else's data.

Used by the MCP server (MARGINALIA_API_KEY env → Bearer header).
"""
import structlog
from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_session
from app.models.installation import Installation
from app.services.api_key import resolve_api_key

logger = structlog.get_logger()


async def optional_installation(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
) -> Installation | None:
    auth = request.headers.get("Authorization", "")
    if not auth:
        return None

    scheme, _, token = auth.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(status_code=401, detail="Expected 'Authorization: Bearer <api key>'")

    installation = await resolve_api_key(db, token.strip())
    if installation is None:
        logger.warning("api_key_rejected", key_prefix=token.strip()[:8])
        raise HTTPException(status_code=401, detail="Invalid or revoked API key")

    return installation