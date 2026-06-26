import hashlib
import hmac
import pytest
from unittest.mock import patch, MagicMock


def compute_signature(secret: str, body: bytes) -> str:
    digest = hmac.new(
        key=secret.encode("utf-8"),
        msg=body,
        digestmod=hashlib.sha256
    ).hexdigest()
    return f"sha256={digest}"


class TestSignatureVerification:

    @pytest.mark.asyncio
    async def test_valid_signature_passes(self):
        from app.middleware.webhook_auth import verify_github_webhook_signature
        from app.config import get_settings

        body = b'{"action": "opened"}'
        secret = "test_webhook_secret"
        valid_sig = compute_signature(secret, body)

        mock_request = MagicMock()
        mock_request.body = AsyncMock(return_value=body)
        mock_request.headers = {"X-Hub-Signature-256": valid_sig}
        mock_request.client.host = "192.30.252.0"
        mock_request.url = "http://localhost:8000/webhooks/github"

        get_settings.cache_clear()

        with patch("app.middleware.webhook_auth.get_settings") as mock_settings:
            mock_settings.return_value.github_webhook_secret = secret
            result = await verify_github_webhook_signature(mock_request)

        assert result == body

    @pytest.mark.asyncio
    async def test_missing_signature_returns_401(self):
        from fastapi import HTTPException
        from app.middleware.webhook_auth import verify_github_webhook_signature

        mock_request = MagicMock()
        mock_request.body = AsyncMock(return_value=b'{"action": "opened"}')
        mock_request.headers = {}
        mock_request.client.host = "1.2.3.4"
        mock_request.url = "http://localhost:8000/webhooks/github"

        with pytest.raises(HTTPException) as exc_info:
            await verify_github_webhook_signature(mock_request)

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_invalid_signature_returns_401(self):
        from fastapi import HTTPException
        from app.middleware.webhook_auth import verify_github_webhook_signature

        body = b'{"action": "opened"}'

        mock_request = MagicMock()
        mock_request.body = AsyncMock(return_value=body)
        mock_request.headers = {
            "X-Hub-Signature-256": "sha256=invalidsignature"
        }
        mock_request.client.host = "1.2.3.4"
        mock_request.url = "http://localhost:8000/webhooks/github"

        with patch("app.middleware.webhook_auth.get_settings") as mock_settings:
            mock_settings.return_value.github_webhook_secret = "real_secret"
            with pytest.raises(HTTPException) as exc_info:
                await verify_github_webhook_signature(mock_request)

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_tampered_body_returns_401(self):
        from fastapi import HTTPException
        from app.middleware.webhook_auth import verify_github_webhook_signature

        secret = "test_secret"
        original_body = b'{"action": "opened"}'
        tampered_body = b'{"action": "closed"}'
        sig = compute_signature(secret, original_body)

        mock_request = MagicMock()
        mock_request.body = AsyncMock(return_value=tampered_body)
        mock_request.headers = {"X-Hub-Signature-256": sig}
        mock_request.client.host = "1.2.3.4"
        mock_request.url = "http://localhost:8000/webhooks/github"

        with patch("app.middleware.webhook_auth.get_settings") as mock_settings:
            mock_settings.return_value.github_webhook_secret = secret
            with pytest.raises(HTTPException) as exc_info:
                await verify_github_webhook_signature(mock_request)

        assert exc_info.value.status_code == 401


# Helper for async mocks
from unittest.mock import AsyncMock