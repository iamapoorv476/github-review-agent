import base64
import structlog
from cryptography.fernet import Fernet
from app.config import get_settings

logger = structlog.get_logger()

_fernet: Fernet | None = None

def get_fernet() -> Fernet:
    """
    Returns shared Fernet encryption instance.
    Fernet uses AES-128-CBC with HMAC-SHA256.
    """

    global _fernet
    if _fernet is None:
        settings = get_settings()

        key_bytes = bytes.fromhex(settings.encryption_key)
        key_b64 = base64.urlsafe_b64encode(key_bytes)
        _fernet = Fernet(key_b64)
    return _fernet 

def encrypt_token(token: str) -> str:
    """Encrypts a plaintext token for database storage."""
    fernet = get_fernet()
    encrypted = fernet.encrypt(token.encode())
    return encrypted.decode()

def decrypt_token(encrypted_token: str) -> str:
    """Decrypts a stored token for use in API calls."""
    fernet = get_fernet()
    decrypted = fernet.decrypt(encrypted_token.encode())
    return decrypted.decode()