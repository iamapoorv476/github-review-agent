import hashlib
import hmac
import structlog
from fastapi import Request, HTTPException
from app.config import get_settings

logger = structlog.get_logger()

async def verify_github_webhook_signature(request: Request) -> bytes:
    """
    Verifies the X-Hub-Signature-256 header on incoming GitHub webhooks.

    Returns the raw body bytes if valid.
    Raises HTTP 401 if signature is missing or invalid.

    CRITICAL: We must read and verify the raw bytes BEFORE any JSON parsing.
    Parsing first and re-serializing changes byte order and breaks HMAC.
    """

    
    settings= get_settings()

    raw_body= await request.body()

    signature_header = request.headers.get("X-Hub-Signature-256")

    if not signature_header:
        logger.warning(
            "webhook_missing_signature",
            path= str(request.url),
            ip=request.client.host if request.client else "unknown"
        )
        raise HTTPException(
            status_code=401,
            detail="Missing X-Hub-Signature-256 header"
        )
    
    if not signature_header.startswith("sha256="):
        logger.warning(
            "webhook_malformed_signature",
            signature_prefix=signature_header[:10]
        )
        raise HTTPException(
            status_code=401,
            detail="Malformed signature header"
        )
    
    provided_digest = signature_header[7:]

    expected_digest = hmac.new(
        key=settings.github_webhook_secret.encode("utf-8"),
        msg=raw_body,
        digestmod=hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(provided_digest, expected_digest):
        logger.warning(
            "webhook_invalid_signature",
            ip=request.client.host if request.client else "unknown"
        )
        raise HTTPException(
            status_code=401,
            detail="Invalid signature"
        )

    logger.debug(
        "webhook_signature_verified",
        content_length=len(raw_body)
    )

    return raw_body